"""Tests for SQLite connection hardening."""

import sqlite3
from types import SimpleNamespace
from typing import Any, cast

from app.core.enums import SQLiteSynchronousMode
from app.database.pragmas import (
    apply_sqlite_pragmas,
    install_sqlite_pragmas,
    sqlite_connect_listener,
)
from sqlalchemy.engine import Engine


def test_apply_sqlite_pragmas_enables_required_guards() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        apply_sqlite_pragmas(
            connection,
            busy_timeout_ms=4321,
            synchronous_mode=SQLiteSynchronousMode.FULL,
        )

        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("PRAGMA busy_timeout").fetchone() == (4321,)
        assert connection.execute("PRAGMA synchronous").fetchone() == (2,)
    finally:
        connection.close()


def test_connect_listener_ignores_unknown_dbapi_connection() -> None:
    listener = sqlite_connect_listener(
        busy_timeout_ms=5000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )

    listener(object(), object())


def test_install_pragmas_ignores_non_sqlite_engine(monkeypatch: Any) -> None:
    calls: list[object] = []
    monkeypatch.setattr("app.database.pragmas.event.listen", lambda *args: calls.append(args))
    fake_engine = cast(Engine, SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))

    install_sqlite_pragmas(
        fake_engine,
        busy_timeout_ms=5000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )

    assert calls == []
