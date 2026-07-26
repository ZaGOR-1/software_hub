"""ORM behavior, relationships, enum persistence and UUID tests."""

from datetime import UTC
from pathlib import Path
from uuid import UUID

from app.core.enums import SQLiteSynchronousMode
from app.database.migrations_helpers import upgrade_database
from app.database.session import Database, create_database_engine
from app.models import (
    Architecture,
    Category,
    FileStatus,
    PackageType,
    ReleaseFile,
    ScannerStatus,
    SignatureStatus,
    Software,
    SoftwareStatus,
    Tag,
    Visibility,
)
from sqlalchemy import select
from tests.fixtures.models import make_catalog_graph


def create_domain_database(tmp_path: Path) -> Database:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'models.db'}"
    upgrade_database(database_url)
    return Database(
        create_database_engine(
            database_url,
            busy_timeout_ms=5_000,
            synchronous_mode=SQLiteSynchronousMode.NORMAL,
        )
    )


def test_complete_catalog_graph_round_trips(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            persisted_file = make_catalog_graph(session)
            public_uuid = persisted_file.public_uuid

        with database.session() as session:
            software = session.scalar(select(Software).where(Software.slug == "7-zip"))
            assert software is not None
            assert software.status is SoftwareStatus.PUBLISHED
            assert software.visibility is Visibility.PUBLIC
            assert software.category is not None
            assert software.category.slug == "7-zip-category"
            assert [tag.slug for tag in software.tags] == ["7-zip-tag"]
            assert len(software.releases) == 1

            release_file = session.scalar(
                select(ReleaseFile).where(ReleaseFile.public_uuid == public_uuid)
            )
            assert release_file is not None
            assert isinstance(release_file.public_uuid, UUID)
            assert release_file.architecture is Architecture.X64
            assert release_file.package_type is PackageType.INSTALLER
            assert release_file.status is FileStatus.PUBLISHED
            assert release_file.signature_status is SignatureStatus.VALID
            assert release_file.scanner_status is ScannerStatus.CLEAN
            assert release_file.created_at.tzinfo is UTC
            assert release_file.updated_at.tzinfo is UTC
            assert release_file.uploaded_at.tzinfo is UTC
            assert release_file.download_stats[0].successful_download_count == 3
    finally:
        database.dispose()


def test_category_delete_sets_software_category_to_null(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            release_file = make_catalog_graph(session)
            software_id = release_file.release.software.id
            category_id = release_file.release.software.category_id

        with database.transaction() as session:
            category = session.get(Category, category_id)
            assert category is not None
            session.delete(category)

        with database.session() as session:
            software = session.get(Software, software_id)
            assert software is not None
            assert software.category_id is None
    finally:
        database.dispose()


def test_deleting_tag_only_removes_association(tmp_path: Path) -> None:
    database = create_domain_database(tmp_path)
    try:
        with database.transaction() as session:
            release_file = make_catalog_graph(session)
            software_id = release_file.release.software.id
            tag_id = release_file.release.software.tags[0].id

        with database.transaction() as session:
            tag = session.get(Tag, tag_id)
            assert tag is not None
            session.delete(tag)

        with database.session() as session:
            software = session.get(Software, software_id)
            assert software is not None
            assert software.tags == []
    finally:
        database.dispose()
