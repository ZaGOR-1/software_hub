"""Integration tests for SQLite PRAGMAs, constraints and concurrency."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app.core.enums import SQLiteSynchronousMode
from app.database.session import Database, create_database_engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def create_database(path: Path, *, timeout_ms: int = 5000) -> Database:
    return Database(
        create_database_engine(
            sqlite_url(path),
            busy_timeout_ms=timeout_ms,
            synchronous_mode=SQLiteSynchronousMode.NORMAL,
        )
    )


def test_file_database_enables_foreign_keys_wal_busy_timeout_and_normal_sync(
    tmp_path: Path,
) -> None:
    database = create_database(tmp_path / "pragmas.db", timeout_ms=3456)
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 3456
            assert connection.execute(text("PRAGMA synchronous")).scalar_one() == 1
    finally:
        database.dispose()


def test_foreign_key_violations_are_enforced(tmp_path: Path) -> None:
    database = create_database(tmp_path / "foreign-keys.db")
    try:
        with database.engine.begin() as connection:
            connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text(
                    "CREATE TABLE child ("
                    "id INTEGER PRIMARY KEY, "
                    "parent_id INTEGER NOT NULL REFERENCES parent(id)"
                    ")"
                )
            )

        with pytest.raises(IntegrityError), database.transaction() as session:
            session.execute(text("INSERT INTO child (parent_id) VALUES (999)"))
    finally:
        database.dispose()


def test_multiple_short_transactions_complete_without_locked_database(tmp_path: Path) -> None:
    database = create_database(tmp_path / "concurrency.db", timeout_ms=10000)
    try:
        with database.engine.begin() as connection:
            connection.execute(text("CREATE TABLE writes (id INTEGER PRIMARY KEY, worker INTEGER)"))

        def write_rows(worker: int) -> None:
            for _ in range(20):
                with database.transaction() as session:
                    session.execute(
                        text("INSERT INTO writes (worker) VALUES (:worker)"),
                        {"worker": worker},
                    )

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(write_rows, range(4)))

        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM writes")).scalar_one() == 80
    finally:
        database.dispose()
