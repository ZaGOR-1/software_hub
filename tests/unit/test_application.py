"""Tests for application construction and bootstrap settings."""

from pathlib import Path

from app.core.config import AppSettings
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_create_app_uses_supplied_metadata() -> None:
    settings = AppSettings(
        app_name="Software Hub Test",
        app_version="9.9.9",
        app_environment="test",
    )

    application = create_app(settings)

    assert isinstance(application, FastAPI)
    assert application.title == "Software Hub Test"
    assert application.version == "9.9.9"
    assert application.state.settings is settings


def test_docs_can_be_disabled(tmp_path: Path) -> None:
    application = create_app(
        AppSettings(
            app_environment="test",
            docs_enabled=False,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'docs.db'}",
        ),
    )

    with TestClient(application) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health").status_code == 200
