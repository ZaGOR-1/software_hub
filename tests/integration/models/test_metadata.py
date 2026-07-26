"""Metadata and schema-shape tests for all Phase 4 models."""

from pathlib import Path

import app.models  # noqa: F401
from app.core.enums import SQLiteSynchronousMode
from app.database.base import Base
from app.database.migrations_helpers import upgrade_database
from app.database.session import Database, create_database_engine
from sqlalchemy import inspect

EXPECTED_TABLES = {
    "alembic_version",
    "audit_logs",
    "categories",
    "download_stats",
    "release_files",
    "releases",
    "sessions",
    "software",
    "software_tags",
    "tags",
    "users",
}


def test_metadata_contains_all_domain_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES - {"alembic_version"}


def test_migration_creates_expected_tables_and_indexes(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'schema.db'}"
    upgrade_database(database_url)
    database = Database(
        create_database_engine(
            database_url,
            busy_timeout_ms=5_000,
            synchronous_mode=SQLiteSynchronousMode.NORMAL,
        )
    )
    try:
        inspector = inspect(database.engine)
        assert set(inspector.get_table_names()) == EXPECTED_TABLES

        release_indexes = {index["name"] for index in inspector.get_indexes("releases")}
        assert "uq_releases_one_current_stable_per_software" in release_indexes
        assert "ix_releases_software_status" in release_indexes

        file_indexes = {index["name"] for index in inspector.get_indexes("release_files")}
        assert "ix_release_files_sha256" in file_indexes
        assert "ix_release_files_status_visibility" in file_indexes
    finally:
        database.dispose()
