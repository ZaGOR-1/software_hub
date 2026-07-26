"""Health, dashboard metrics and status failure coverage for Phase 15."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.models import DownloadStat, Release, ReleaseFile, Software
from app.models.enums import (
    FileStatus,
    ReleaseChannel,
    ReleaseStatus,
    SoftwareStatus,
    Visibility,
)
from app.services.auth_service import AuthService
from app.services.dashboard_service import DashboardService
from app.services.system_status_service import ComponentState
from app.storage.disk import DiskSpace
from fastapi import FastAPI
from fastapi.testclient import TestClient

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def _login(application: FastAPI, client: TestClient) -> None:
    AuthService(application.state.database, application.state.settings).create_admin(
        username="status-admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    match = _CSRF_PATTERN.search(page.text)
    assert match is not None
    response = client.post(
        "/admin/login",
        data={
            "username": "status-admin",
            "password": "correct horse battery staple",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _seed_metrics(application: FastAPI) -> None:
    with application.state.database.transaction() as session:
        software = Software(
            name="Metrics Tool",
            slug="metrics-tool",
            short_description="Operational metrics seed.",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        release = Release(
            software=software,
            version="1.0",
            release_channel=ReleaseChannel.STABLE,
            status=ReleaseStatus.PUBLISHED,
        )
        published = ReleaseFile(
            release=release,
            original_filename="metrics.zip",
            display_filename="metrics.zip",
            storage_filename="a" * 32 + ".zip",
            relative_storage_path="aa/aa/" + "a" * 32 + ".zip",
            file_extension=".zip",
            detected_mime_type="application/zip",
            file_size_bytes=100,
            sha256="a" * 64,
            platform="Windows",
            status=FileStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
            download_count=12,
        )
        disabled = ReleaseFile(
            release=release,
            original_filename="disabled.zip",
            display_filename="disabled.zip",
            storage_filename="b" * 32 + ".zip",
            relative_storage_path="bb/bb/" + "b" * 32 + ".zip",
            file_extension=".zip",
            detected_mime_type="application/zip",
            file_size_bytes=100,
            sha256="b" * 64,
            platform="Windows",
            status=FileStatus.DISABLED,
            visibility=Visibility.PRIVATE,
        )
        ready = ReleaseFile(
            release=release,
            original_filename="ready.zip",
            display_filename="ready.zip",
            storage_filename="c" * 32 + ".zip",
            relative_storage_path="cc/cc/" + "c" * 32 + ".zip",
            file_extension=".zip",
            detected_mime_type="application/zip",
            file_size_bytes=100,
            sha256="c" * 64,
            platform="Windows",
            status=FileStatus.READY,
            visibility=Visibility.PRIVATE,
        )
        session.add_all([published, disabled, ready])
        session.flush()
        session.add(
            DownloadStat(
                release_file_id=published.id,
                date=datetime.now(UTC).date(),
                download_count=4,
                successful_download_count=4,
                blocked_download_count=2,
            )
        )


def test_health_exposes_only_bounded_component_states(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["checks"] == {
        "application": "ok",
        "database": "ok",
        "storage": "ok",
        "disk": "ok",
    }
    serialized = response.text
    assert "/srv/" not in serialized
    assert "free_bytes" not in serialized
    assert "database_url" not in serialized


def test_health_returns_generic_503_for_database_failure(
    application: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(application.state.database, "ping", lambda: False)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "The service is not ready."
    assert "sqlite" not in response.text.lower()
    assert str(application.state.settings.database_url) not in response.text


def test_health_returns_generic_503_for_missing_storage(
    application: FastAPI,
    client: TestClient,
) -> None:
    application.state.storage.paths.icons.rmdir()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert str(application.state.storage.paths.icons) not in response.text


def test_health_returns_generic_503_below_disk_reserve(
    application: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application.state.storage.minimum_free_bytes = 100
    monkeypatch.setattr(
        "app.services.system_status_service.get_disk_space",
        lambda _path: DiskSpace(total=1000, used=950, free=50),
    )

    response = client.get("/health")

    assert response.status_code == 503
    error = response.json()["error"]
    assert set(error) == {"code", "message", "request_id"}
    assert error["code"] == "service_unavailable"
    assert error["message"] == "The service is not ready."
    assert "free_bytes" not in response.text
    assert "minimum_free_bytes" not in response.text


def test_dashboard_metrics_status_and_backup_manifest(
    application: FastAPI,
    client: TestClient,
) -> None:
    _seed_metrics(application)
    manifest = (
        Path(application.state.storage.paths.backups)
        / "software-hub-backup-20260724T120000Z"
        / "manifest.json"
    )
    manifest.parent.mkdir()
    manifest.write_text("{}", encoding="utf-8")
    _login(application, client)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "12" in response.text
    assert "4" in response.text
    assert "2" in response.text
    assert "На перевірці" in response.text
    assert "Вимкнених файлів" in response.text
    assert "База даних доступна" in response.text
    assert "Сховище доступне" in response.text
    assert "Підтверджений manifest ще не знайдено" not in response.text
    assert str(application.state.storage.paths.root) not in response.text
    assert 'href="/admin/audit"' in response.text


def test_dashboard_service_empty_catalog_is_bounded(
    application: FastAPI,
    client: TestClient,
) -> None:
    assert client.get("/health").status_code == 200
    snapshot = DashboardService(
        application.state.database,
        application.state.storage,
    ).snapshot()

    assert snapshot.software_count == 0
    assert snapshot.release_count == 0
    assert snapshot.file_count == 0
    assert snapshot.total_downloads == 0
    assert snapshot.system.database.state is ComponentState.OK
    assert snapshot.system.storage.state is ComponentState.OK
