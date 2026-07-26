"""Unit tests for programmatic Alembic configuration."""

from app.database.migrations_helpers import ALEMBIC_CONFIG_PATH, build_alembic_config


def test_build_alembic_config_uses_repository_config_and_private_url_attribute() -> None:
    database_url = "sqlite+pysqlite:///:memory:"

    config = build_alembic_config(database_url)

    assert ALEMBIC_CONFIG_PATH.is_file()
    assert config.config_file_name == str(ALEMBIC_CONFIG_PATH)
    assert config.attributes["database_url"] == database_url
    assert config.attributes["configure_logger"] is False
