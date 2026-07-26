"""Browser-level lifecycle routes for release files."""

from __future__ import annotations

import re
from typing import cast
from urllib.parse import urlsplit

from app.models import AuditLog, Release, ReleaseFile, Software
from app.models.enums import FileStatus, ReleaseStatus, SoftwareStatus, Visibility
from app.services.auth_service import AuthService
from app.storage.lifecycle import StorageArea, locate_stored_file
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


def _published_release(application: FastAPI, slug: str) -> int:
    with application.state.database.transaction() as session:
        software = Software(
            name=f"Lifecycle {slug}",
            slug=slug,
            short_description="Route lifecycle",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        release = Release(
            software=software,
            version="1.0",
            status=ReleaseStatus.PUBLISHED,
        )
        session.add(software)
        session.flush()
        return release.id


def _upload(
    client: TestClient,
    *,
    release_id: int,
    filename: str,
    body: bytes,
) -> str:
    page = client.get(f"/admin/releases/{release_id}/files/new")
    response = client.post(
        f"/admin/releases/{release_id}/files",
        data={
            "csrf_token": _csrf(page.text),
            "architecture": "x64",
            "package_type": "archive",
            "platform": "Windows",
            "visibility": "public",
        },
        files={"file": (filename, body, "application/octet-stream")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return urlsplit(response.headers["location"]).path


def _post_action(client: TestClient, detail_url: str, action: str) -> None:
    page = client.get(detail_url)
    response = client.post(
        f"{detail_url}/{action}",
        data={"csrf_token": _csrf(page.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _status(application: FastAPI, file_id: int) -> FileStatus:
    with application.state.database.session() as session:
        record = session.get(ReleaseFile, file_id)
        assert record is not None
        return cast(FileStatus, record.status)


def test_publish_disable_restore_archive_and_verify_routes(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _published_release(application, "route-lifecycle")
    detail_url = _upload(
        client,
        release_id=release_id,
        filename="tool.zip",
        body=b"PK\x03\x04route-lifecycle",
    )

    detail = client.get(detail_url)
    assert "Майбутній публічний URL" in detail.text
    assert "/download/" in detail.text
    assert "quarantine" in detail.text

    _post_action(client, detail_url, "verify")
    _post_action(client, detail_url, "publish")
    file_id = int(detail_url.rsplit("/", 1)[1])
    with application.state.database.session() as session:
        record = session.get(ReleaseFile, file_id)
        assert record is not None
        assert record.status is FileStatus.PUBLISHED
        relative = record.relative_storage_path
    stored = locate_stored_file(application.state.storage.paths, relative)
    assert stored.area is StorageArea.SOFTWARE

    _post_action(client, detail_url, "disable")
    _post_action(client, detail_url, "restore")
    stored = locate_stored_file(application.state.storage.paths, relative)
    assert stored.area is StorageArea.QUARANTINE
    _post_action(client, detail_url, "archive")

    with application.state.database.session() as session:
        record = session.get(ReleaseFile, file_id)
        assert record is not None
        assert record.status is FileStatus.ARCHIVED
        actions = set(session.scalars(select(AuditLog.action)))
    assert {
        "file_verified",
        "file_published",
        "file_disabled",
        "file_restored",
        "file_archived",
    }.issubset(actions)


def test_manual_review_routes(application: FastAPI, client: TestClient) -> None:
    _login(application, client)
    release_id = _published_release(application, "manual-review")
    detail_url = _upload(
        client,
        release_id=release_id,
        filename="unknown.zip",
        body=b"not-a-known-signature",
    )
    file_id = int(detail_url.rsplit("/", 1)[1])

    assert _status(application, file_id) is FileStatus.QUARANTINE

    _post_action(client, detail_url, "review/approve")
    assert _status(application, file_id) is FileStatus.READY

    _post_action(client, detail_url, "review/reject")
    assert _status(application, file_id) is FileStatus.REJECTED

    _post_action(client, detail_url, "review/reopen")
    assert _status(application, file_id) is FileStatus.QUARANTINE


def test_metadata_and_permanent_delete_routes(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)
    release_id = _published_release(application, "delete-routes")

    metadata_url = _upload(
        client,
        release_id=release_id,
        filename="metadata.zip",
        body=b"PK\x03\x04metadata-only",
    )
    metadata_id = int(metadata_url.rsplit("/", 1)[1])
    page = client.get(metadata_url)
    invalid = client.post(
        f"{metadata_url}/delete-metadata",
        data={"csrf_token": _csrf(page.text), "confirmation": "wrong"},
    )
    assert invalid.status_code == 422

    page = client.get(metadata_url)
    deleted = client.post(
        f"{metadata_url}/delete-metadata",
        data={"csrf_token": _csrf(page.text), "confirmation": "DELETE METADATA"},
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    with application.state.database.session() as session:
        assert session.get(ReleaseFile, metadata_id) is None

    permanent_url = _upload(
        client,
        release_id=release_id,
        filename="permanent.zip",
        body=b"PK\x03\x04permanent",
    )
    permanent_id = int(permanent_url.rsplit("/", 1)[1])
    with application.state.database.session() as session:
        record = session.get(ReleaseFile, permanent_id)
        assert record is not None
        relative = record.relative_storage_path

    page = client.get(permanent_url)
    deleted = client.post(
        f"{permanent_url}/delete-permanently",
        data={"csrf_token": _csrf(page.text), "confirmation": "DELETE FILE"},
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    with application.state.database.session() as session:
        assert session.get(ReleaseFile, permanent_id) is None
    assert not locate_optional(application, relative)


def locate_optional(application: FastAPI, relative: str) -> bool:
    from app.storage.lifecycle import inspect_stored_files

    return bool(inspect_stored_files(application.state.storage.paths, relative))
