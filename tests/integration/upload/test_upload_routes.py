"""Admin upload HTTP workflow with CSRF, quarantine and safe rendering."""

import re

from app.models import AuditLog, Release, ReleaseFile, Software
from app.models.enums import FileStatus, ScannerStatus
from app.services.auth_service import AuthService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf(html: str) -> str:
    match = _CSRF_PATTERN.search(html)
    assert match is not None
    return match.group(1)


def _login(application: FastAPI, client: TestClient) -> None:
    AuthService(application.state.database, application.state.settings).create_admin(
        username="admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct horse battery staple",
            "csrf_token": _csrf(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _release(application: FastAPI) -> int:
    with application.state.database.transaction() as session:
        software = Software(
            name="Route Tool",
            slug="route-tool",
            short_description="Route upload test",
        )
        release = Release(software=software, version="1.0")
        session.add(software)
        session.flush()
        return release.id


def test_upload_route_ignores_client_mime_and_shows_quarantine_metadata(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _release(application)
    page = client.get(f"/admin/releases/{release_id}/files/new")
    assert page.status_code == 200
    token = _csrf(page.text)

    response = client.post(
        f"/admin/releases/{release_id}/files",
        data={
            "csrf_token": token,
            "display_filename": "Route Tool.zip",
            "architecture": "x64",
            "package_type": "archive",
            "platform": "Windows",
            "visibility": "private",
            "source_url": "https://example.com/tool",
            "admin_note": "<script>alert(1)</script>",
        },
        files={"file": ("route-tool.zip", b"PK\x03\x04payload", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/files/")

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "application/zip" in detail.text
    assert "unavailable" in detail.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail.text
    assert "<script>alert(1)</script>" not in detail.text

    with application.state.database.session() as session:
        release_file = session.scalar(select(ReleaseFile))
        assert release_file is not None
        assert release_file.status is FileStatus.READY
        assert release_file.scanner_status is ScannerStatus.UNAVAILABLE
        assert release_file.detected_mime_type == "application/zip"
        actions = set(session.scalars(select(AuditLog.action)))
        assert "file_uploaded" in actions


def test_upload_route_requires_file_and_valid_extension(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _release(application)
    page = client.get(f"/admin/releases/{release_id}/files/new")
    token = _csrf(page.text)

    missing = client.post(
        f"/admin/releases/{release_id}/files",
        data={"csrf_token": token, "platform": "Windows"},
    )
    assert missing.status_code == 422
    assert "Виберіть файл" in missing.text

    page = client.get(f"/admin/releases/{release_id}/files/new")
    invalid = client.post(
        f"/admin/releases/{release_id}/files",
        data={"csrf_token": _csrf(page.text), "platform": "Windows"},
        files={"file": ("payload.pdf.exe", b"MZ", "application/octet-stream")},
    )
    assert invalid.status_code == 422
    assert "double extensions" in invalid.text


def test_upload_content_length_precheck_returns_413(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _release(application)
    page = client.get(f"/admin/releases/{release_id}/files/new")
    response = client.post(
        f"/admin/releases/{release_id}/files",
        data={"csrf_token": _csrf(page.text), "platform": "Windows"},
        files={"file": ("small.zip", b"PK\x03\x04", "application/zip")},
        headers={"content-length": str(application.state.settings.max_upload_size + 3_000_000)},
    )
    assert response.status_code == 413


def test_duplicate_detail_uses_eager_loaded_release_metadata(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _release(application)
    body = b"PK\x03\x04duplicate-body"
    locations: list[str] = []

    for filename in ("first.zip", "second.zip"):
        page = client.get(f"/admin/releases/{release_id}/files/new")
        response = client.post(
            f"/admin/releases/{release_id}/files",
            data={
                "csrf_token": _csrf(page.text),
                "architecture": "x64",
                "package_type": "archive",
                "platform": "Windows",
                "visibility": "private",
            },
            files={"file": (filename, body, "application/octet-stream")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        locations.append(response.headers["location"])

    detail = client.get(locations[1])
    assert detail.status_code == 200
    assert "Дублікати SHA-256" in detail.text
    assert "first.zip" in detail.text
    assert "1.0" in detail.text


def test_upload_multipart_parser_rejects_multiple_files(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _release(application)
    page = client.get(f"/admin/releases/{release_id}/files/new")
    response = client.post(
        f"/admin/releases/{release_id}/files",
        data={"csrf_token": _csrf(page.text), "platform": "Windows"},
        files=[
            ("file", ("one.zip", b"PK\x03\x04one", "application/zip")),
            ("file", ("two.zip", b"PK\x03\x04two", "application/zip")),
        ],
    )
    assert response.status_code == 400
