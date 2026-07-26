"""Tests for the Phase 1 liveness endpoint."""

from app import __version__
from fastapi.testclient import TestClient


def test_health_returns_service_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "software-hub",
        "version": __version__,
        "checks": {
            "application": "ok",
            "database": "ok",
            "storage": "ok",
            "disk": "ok",
        },
    }


def test_health_response_is_json(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["content-type"] == "application/json"
