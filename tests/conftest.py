"""Shared pytest fixtures."""

from collections.abc import Generator
from pathlib import Path

import pytest
from app.core.config import AppSettings, get_settings
from app.core.enums import SQLiteSynchronousMode
from app.database.migrations_helpers import upgrade_database
from app.database.session import Database, create_database_engine
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def test_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        app_environment="test",
        app_debug=False,
        docs_enabled=True,
        app_secret_key="test-app-secret-0123456789-ABCDEFGH",
        csrf_secret="test-csrf-secret-9876543210-HGFEDCBA",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        argon2_time_cost=1,
        argon2_memory_cost_kib=1_024,
        argon2_parallelism=1,
        session_touch_interval_seconds=1,
        storage_root=tmp_path / "storage",
        temporary_root=tmp_path / "storage" / "temporary",
        quarantine_root=tmp_path / "storage" / "quarantine",
        icons_root=tmp_path / "storage" / "icons",
        backup_root=tmp_path / "backups",
        storage_min_free_bytes=0,
    )


@pytest.fixture
def application(test_settings: AppSettings) -> Generator[FastAPI]:
    upgrade_database(test_settings.database_url)
    app = create_app(test_settings)
    try:
        yield app
    finally:
        app.state.database.dispose()


@pytest.fixture
def client(application: FastAPI) -> Generator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def domain_database(tmp_path: Path) -> Generator[Database]:
    """Provide a migrated file-backed database for repository/service tests."""

    database_url = f"sqlite+pysqlite:///{tmp_path / 'domain.db'}"
    upgrade_database(database_url)
    database = Database(
        create_database_engine(
            database_url,
            busy_timeout_ms=5_000,
            synchronous_mode=SQLiteSynchronousMode.NORMAL,
        )
    )
    try:
        yield database
    finally:
        database.dispose()
