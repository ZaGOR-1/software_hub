"""Programmatic Alembic helpers used by tests and future maintenance commands."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext

from app.core.enums import SQLiteSynchronousMode
from app.database.session import create_database_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG_PATH = PROJECT_ROOT / "alembic.ini"


def build_alembic_config(database_url: str) -> Config:
    """Build an Alembic configuration without exposing the URL in logs."""

    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


def upgrade_database(database_url: str, revision: str = "head") -> None:
    """Upgrade a database to the requested migration revision."""

    command.upgrade(build_alembic_config(database_url), revision)


def downgrade_database(database_url: str, revision: str = "base") -> None:
    """Downgrade a database to the requested migration revision."""

    command.downgrade(build_alembic_config(database_url), revision)


def check_database_schema(database_url: str) -> None:
    """Fail when ORM metadata contains changes missing from Alembic migrations."""

    command.check(build_alembic_config(database_url))


def get_current_revision(database_url: str) -> str | None:
    """Read the database revision without modifying schema state."""

    engine = create_database_engine(
        database_url,
        busy_timeout_ms=5_000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
