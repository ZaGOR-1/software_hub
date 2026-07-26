"""Alembic environment configured through Software Hub settings."""

from logging.config import fileConfig

from alembic import context
from app import models as _models  # noqa: F401
from app.core.config import AppSettings
from app.database.base import Base
from app.database.session import create_database_engine
from sqlalchemy.engine import Connection

config = context.config
target_metadata = Base.metadata

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def database_url() -> str:
    """Resolve an explicit test URL or the normal typed application setting."""

    explicit_url = config.attributes.get("database_url")
    if isinstance(explicit_url, str):
        return explicit_url
    return AppSettings().database_url


def configure_context(connection: Connection) -> None:
    """Configure migration comparison consistently for SQLite and future DBs."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""

    url = database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the same hardened engine policy as the app."""

    settings = AppSettings()
    engine = create_database_engine(
        database_url(),
        busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        synchronous_mode=settings.sqlite_synchronous_mode,
        echo=settings.database_echo,
    )
    try:
        with engine.connect() as connection:
            configure_context(connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
