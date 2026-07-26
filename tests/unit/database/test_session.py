"""Unit tests for engine and request-session infrastructure."""

import logging
from pathlib import Path

import pytest
from app.core.config import AppSettings
from app.core.enums import SQLiteSynchronousMode
from app.database.session import (
    Database,
    create_database,
    create_database_engine,
    get_database,
    get_db_session,
)
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from starlette.requests import Request


def sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def test_memory_database_uses_static_pool() -> None:
    engine = create_database_engine(
        "sqlite+pysqlite:///:memory:",
        busy_timeout_ms=5000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )
    try:
        assert isinstance(engine.pool, StaticPool)
    finally:
        engine.dispose()


def test_create_database_uses_validated_settings(tmp_path: Path) -> None:
    settings = AppSettings(
        _env_file=None,
        app_environment="test",
        database_url=sqlite_url(tmp_path / "settings.db"),
        sqlite_busy_timeout_ms=2345,
    )
    database = create_database(settings)
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 2345
    finally:
        database.dispose()


def test_transaction_commits_and_rolls_back(tmp_path: Path) -> None:
    engine = create_database_engine(
        sqlite_url(tmp_path / "transactions.db"),
        busy_timeout_ms=5000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )
    database = Database(engine)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)"))

        with database.transaction() as session:
            session.execute(text("INSERT INTO sample (value) VALUES ('committed')"))

        def insert_then_fail() -> None:
            with database.transaction() as session:
                session.execute(text("INSERT INTO sample (value) VALUES ('rolled-back')"))
                raise RuntimeError("rollback")

        with pytest.raises(RuntimeError, match="rollback"):
            insert_then_fail()

        with engine.connect() as connection:
            values = (
                connection.execute(text("SELECT value FROM sample ORDER BY id")).scalars().all()
            )
        assert values == ["committed"]
    finally:
        database.dispose()


def test_ping_returns_false_without_logging_physical_path(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("x", encoding="utf-8")
    engine = create_database_engine(
        sqlite_url(parent_file / "database.db"),
        busy_timeout_ms=5000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )
    database = Database(engine)
    try:
        with caplog.at_level(logging.WARNING):
            assert database.ping() is False
        assert getattr(caplog.records[-1], "exception_type", None) == "OperationalError"
        assert str(parent_file) not in caplog.text
    finally:
        database.dispose()


def test_get_database_reads_application_state(tmp_path: Path) -> None:
    app = FastAPI()
    settings = AppSettings(
        _env_file=None,
        app_environment="test",
        database_url=sqlite_url(tmp_path / "state.db"),
    )
    database = create_database(settings)
    app.state.database = database
    request = Request({"type": "http", "app": app, "headers": []})
    try:
        assert get_database(request) is database
    finally:
        database.dispose()


def test_get_database_fails_when_not_initialized() -> None:
    request = Request({"type": "http", "app": FastAPI(), "headers": []})

    with pytest.raises(RuntimeError, match="not initialized"):
        get_database(request)


def test_request_session_dependency_yields_usable_session(tmp_path: Path) -> None:
    engine = create_database_engine(
        sqlite_url(tmp_path / "dependency.db"),
        busy_timeout_ms=5000,
        synchronous_mode=SQLiteSynchronousMode.NORMAL,
    )
    database = Database(engine)
    dependency = get_db_session(database)
    try:
        session = next(dependency)
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        dependency.close()
        database.dispose()
