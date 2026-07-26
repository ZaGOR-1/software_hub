"""SQLite connection hardening applied to every DB-API connection."""

import sqlite3
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.enums import SQLiteSynchronousMode


def apply_sqlite_pragmas(
    connection: sqlite3.Connection,
    *,
    busy_timeout_ms: int,
    synchronous_mode: SQLiteSynchronousMode,
) -> None:
    """Apply required SQLite safety and concurrency PRAGMAs."""

    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms:d}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA synchronous={synchronous_mode.value}")
    finally:
        cursor.close()


def sqlite_connect_listener(
    *,
    busy_timeout_ms: int,
    synchronous_mode: SQLiteSynchronousMode,
) -> Callable[[object, object], None]:
    """Build a SQLAlchemy connect listener with validated immutable settings."""

    def on_connect(dbapi_connection: object, connection_record: object) -> None:
        del connection_record
        if isinstance(dbapi_connection, sqlite3.Connection):
            apply_sqlite_pragmas(
                dbapi_connection,
                busy_timeout_ms=busy_timeout_ms,
                synchronous_mode=synchronous_mode,
            )

    return on_connect


def install_sqlite_pragmas(
    engine: Engine,
    *,
    busy_timeout_ms: int,
    synchronous_mode: SQLiteSynchronousMode,
) -> None:
    """Register SQLite PRAGMAs before the engine opens its first connection."""

    if engine.dialect.name != "sqlite":
        return
    event.listen(
        engine,
        "connect",
        sqlite_connect_listener(
            busy_timeout_ms=busy_timeout_ms,
            synchronous_mode=synchronous_mode,
        ),
    )
