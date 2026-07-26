"""Integration tests for database readiness reporting."""

from pathlib import Path

from app.core.config import AppSettings
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_returns_safe_503_when_database_is_unavailable(tmp_path: Path) -> None:
    parent_file = tmp_path / "blocked"
    parent_file.write_text("not a directory", encoding="utf-8")
    settings = AppSettings(
        _env_file=None,
        app_environment="test",
        database_url=f"sqlite+pysqlite:///{parent_file / 'database.db'}",
    )
    application = create_app(settings)

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert response.json()["error"]["message"] == "The service is not ready."
    assert str(parent_file) not in response.text
