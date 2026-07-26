"""Database-enforced uniqueness, check constraints and cascade rules."""

from datetime import date
from pathlib import Path

import pytest
from app.core.enums import SQLiteSynchronousMode
from app.database.migrations_helpers import upgrade_database
from app.database.session import Database, create_database_engine
from app.models import (
    AuditLog,
    Category,
    DownloadStat,
    Release,
    ReleaseChannel,
    ReleaseFile,
    ReleaseStatus,
    Software,
    Tag,
    User,
    UserSession,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from tests.fixtures.models import make_catalog_graph, make_session, make_user


def create_domain_database(tmp_path: Path) -> Database:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'constraints.db'}"
    upgrade_database(database_url)
    return Database(
        create_database_engine(
            database_url,
            busy_timeout_ms=5_000,
            synchronous_mode=SQLiteSynchronousMode.NORMAL,
        )
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (Category(name="A", slug="same"), Category(name="B", slug="same")),
        (Tag(name="A", slug="same"), Tag(name="B", slug="same")),
        (
            User(username="same", password_hash="hash"),
            User(username="same", password_hash="other"),
        ),
    ],
)
def test_unique_identifiers_are_enforced(tmp_path: Path, first: object, second: object) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.session() as session:
            session.add_all([first, second])
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_release_version_channel_is_unique_per_software(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.session() as session:
            software = Software(name="App", slug="app", short_description="App")
            software.releases.extend(
                [
                    Release(version="1.0", release_channel=ReleaseChannel.STABLE),
                    Release(version="1.0", release_channel=ReleaseChannel.STABLE),
                ]
            )
            session.add(software)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_only_one_current_stable_release_per_software(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.session() as session:
            software = Software(name="App", slug="app", short_description="App")
            software.releases.extend(
                [
                    Release(
                        version="1.0",
                        release_channel=ReleaseChannel.STABLE,
                        is_current=True,
                        status=ReleaseStatus.PUBLISHED,
                    ),
                    Release(
                        version="2.0",
                        release_channel=ReleaseChannel.STABLE,
                        is_current=True,
                        status=ReleaseStatus.PUBLISHED,
                    ),
                ]
            )
            session.add(software)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_multiple_current_non_stable_releases_are_allowed(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            software = Software(name="App", slug="app", short_description="App")
            software.releases.extend(
                [
                    Release(version="1.0b1", release_channel=ReleaseChannel.BETA, is_current=True),
                    Release(version="1.0a1", release_channel=ReleaseChannel.ALPHA, is_current=True),
                ]
            )
            session.add(software)
    finally:
        database.dispose()


def test_release_file_and_stat_check_constraints(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.session() as session:
            release_file = make_catalog_graph(session)
            release_file.file_size_bytes = -1
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with database.session() as session:
            release_file = make_catalog_graph(session, slug="bad-sha")
            release_file.sha256 = "too-short"
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with database.session() as session:
            release_file = make_catalog_graph(session, slug="bad-stat")
            release_file.download_stats.append(
                DownloadStat(
                    date=date(2026, 7, 24),
                    download_count=-1,
                    successful_download_count=0,
                    blocked_download_count=0,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_deleting_software_cascades_dependent_metadata(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            release_file = make_catalog_graph(session)
            software_id = release_file.release.software.id

        with database.transaction() as session:
            software = session.get(Software, software_id)
            assert software is not None
            session.delete(software)

        with database.session() as session:
            assert session.scalar(select(func.count()).select_from(Release)) == 0
            assert session.scalar(select(func.count()).select_from(ReleaseFile)) == 0
            assert session.scalar(select(func.count()).select_from(DownloadStat)) == 0
    finally:
        database.dispose()


def test_user_delete_cascades_sessions_and_preserves_audit_log(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            user = make_user()
            user.sessions.append(make_session(user))
            audit = AuditLog(
                user=user,
                action="software_created",
                entity_type="software",
                entity_id="1",
                result="success",
                safe_metadata={"slug": "7-zip"},
            )
            session.add_all([user, audit])
            session.flush()
            user_id = user.id
            audit_id = audit.id

        with database.transaction() as session:
            stored_user = session.get(User, user_id)
            assert stored_user is not None
            session.delete(stored_user)

        with database.session() as session:
            assert session.scalar(select(func.count()).select_from(UserSession)) == 0
            stored_audit = session.get(AuditLog, audit_id)
            assert stored_audit is not None
            assert stored_audit.user_id is None
            assert stored_audit.safe_metadata == {"slug": "7-zip"}
    finally:
        database.dispose()


def test_software_slug_is_unique(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.session() as session:
            session.add_all(
                [
                    Software(name="First", slug="same-app", short_description="First"),
                    Software(name="Second", slug="same-app", short_description="Second"),
                ]
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_session_token_hash_is_unique(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.session() as session:
            first_user = make_user(username="first")
            second_user = make_user(username="second")
            first_user.sessions.append(make_session(first_user, token_hash="f" * 64))
            second_user.sessions.append(make_session(second_user, token_hash="f" * 64))
            session.add_all([first_user, second_user])
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_release_file_public_uuid_and_storage_paths_are_unique(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            first_file = make_catalog_graph(session)
            first_uuid = first_file.public_uuid
            first_storage_name = first_file.storage_filename
            first_storage_path = first_file.relative_storage_path

        with database.session() as session:
            second_file = make_catalog_graph(session, slug="duplicate-file")
            second_file.public_uuid = first_uuid
            second_file.storage_filename = first_storage_name
            second_file.relative_storage_path = first_storage_path
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()


def test_download_stat_is_unique_per_file_and_day(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            release_file = make_catalog_graph(session)
            release_file_id = release_file.id

        with database.session() as session:
            session.add(
                DownloadStat(
                    release_file_id=release_file_id,
                    date=date(2026, 7, 23),
                    download_count=1,
                    successful_download_count=1,
                    blocked_download_count=0,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database.dispose()
