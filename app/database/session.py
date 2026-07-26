"""SQLAlchemy engine, sessions, transaction boundaries and FastAPI dependencies."""

import logging
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings
from app.core.enums import SQLiteSynchronousMode
from app.database.pragmas import install_sqlite_pragmas

logger = logging.getLogger(__name__)


def create_database_engine(
    database_url: str,
    *,
    busy_timeout_ms: int,
    synchronous_mode: SQLiteSynchronousMode,
    echo: bool = False,
) -> Engine:
    """Create a hardened SQLAlchemy engine for the configured SQLite database."""

    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        connect_args = {
            "check_same_thread": False,
            "timeout": busy_timeout_ms / 1000,
        }
        if url.database in {None, "", ":memory:"}:
            engine = create_engine(
                database_url,
                connect_args=connect_args,
                echo=echo,
                future=True,
                pool_pre_ping=True,
                poolclass=StaticPool,
            )
        else:
            engine = create_engine(
                database_url,
                connect_args=connect_args,
                echo=echo,
                future=True,
                pool_pre_ping=True,
            )
    else:
        engine = create_engine(
            database_url,
            echo=echo,
            future=True,
            pool_pre_ping=True,
        )
    install_sqlite_pragmas(
        engine,
        busy_timeout_ms=busy_timeout_ms,
        synchronous_mode=synchronous_mode,
    )
    return engine


class Database:
    """Own one engine and its short-lived SQLAlchemy sessions."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.session_factory = sessionmaker(
            bind=engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )

    def session(self) -> Session:
        """Return a new unit-of-work session without auto-commit behavior."""

        return self.session_factory()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Provide a short transaction that commits or rolls back atomically."""

        with self.session_factory.begin() as session:
            yield session

    def ping(self) -> bool:
        """Check database connectivity without leaking driver details."""

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning(
                "database_health_check_failed",
                extra={"exception_type": type(exc).__name__},
            )
            return False
        return True

    def dispose(self) -> None:
        """Release all pooled database connections."""

        self.engine.dispose()


def create_database(settings: AppSettings) -> Database:
    """Create the process-level database owner from validated settings."""

    engine = create_database_engine(
        settings.database_url,
        busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        synchronous_mode=settings.sqlite_synchronous_mode,
        echo=settings.database_echo,
    )
    return Database(engine)


def get_database(request: Request) -> Database:
    """Resolve the application-owned database from request state."""

    database = getattr(request.app.state, "database", None)
    if not isinstance(database, Database):
        raise RuntimeError("Database infrastructure is not initialized.")  # noqa: TRY004
    return database


def get_db_session(
    database: Annotated[Database, Depends(get_database)],
) -> Generator[Session]:
    """Yield one request-scoped session and always release its resources."""

    with database.session() as session:
        yield session


DatabaseDependency = Annotated[Database, Depends(get_database)]
SessionDependency = Annotated[Session, Depends(get_db_session)]
