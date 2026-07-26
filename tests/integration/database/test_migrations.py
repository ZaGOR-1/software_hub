"""Integration tests for the complete Alembic migration chain."""

from pathlib import Path

from app.database.migrations_helpers import (
    check_database_schema,
    downgrade_database,
    get_current_revision,
    upgrade_database,
)


def test_baseline_migration_upgrades_and_downgrades_clean_database(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migrations.db'}"

    assert get_current_revision(database_url) is None

    upgrade_database(database_url)
    assert get_current_revision(database_url) == "0002_phase4_domain_schema"
    check_database_schema(database_url)

    downgrade_database(database_url)
    assert get_current_revision(database_url) is None
