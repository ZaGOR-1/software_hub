"""Public download authorization, headers and accounting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest
from app.core.config import AppSettings
from app.models.download_stat import DownloadStat
from app.models.enums import FileStatus, ReleaseStatus, SoftwareStatus, Visibility
from app.models.release_file import ReleaseFile
from app.services.auth_service import AuthService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.fixtures.models import make_catalog_graph

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')
_PAYLOAD = b"phase-12-download-payload"


@dataclass(frozen=True, slots=True)
class DownloadFixture:
    file_id: int
    public_uuid: UUID
    display_filename: str
    relative_path: str


def _create_download_fixture(  # noqa: PLR0913
    application: FastAPI,
    *,
    slug: str,
    file_visibility: Visibility = Visibility.PUBLIC,
    software_visibility: Visibility = Visibility.PUBLIC,
    file_status: FileStatus = FileStatus.PUBLISHED,
    release_status: ReleaseStatus = ReleaseStatus.PUBLISHED,
    software_status: SoftwareStatus = SoftwareStatus.PUBLISHED,
    area: Literal["software", "quarantine"] = "software",
    payload: bytes = _PAYLOAD,
) -> DownloadFixture:
    storage_filename = f"{uuid4().hex}.zip"
    relative_path = f"{storage_filename[:2]}/{storage_filename[2:4]}/{storage_filename}"
    display_filename = f"{slug} Українська.zip"
    with application.state.database.transaction() as session:
        release_file = make_catalog_graph(session, slug=slug)
        release_file.display_filename = display_filename
        release_file.original_filename = f"{slug}.zip"
        release_file.storage_filename = storage_filename
        release_file.relative_storage_path = relative_path
        release_file.file_extension = ".zip"
        release_file.detected_mime_type = "application/zip"
        release_file.file_size_bytes = len(payload)
        release_file.download_count = 0
        release_file.download_stats.clear()
        release_file.status = file_status
        release_file.visibility = file_visibility
        release_file.release.status = release_status
        release_file.release.software.status = software_status
        release_file.release.software.visibility = software_visibility
        fixture = DownloadFixture(
            file_id=release_file.id,
            public_uuid=release_file.public_uuid,
            display_filename=display_filename,
            relative_path=relative_path,
        )

    root: Path = (
        application.state.storage.paths.software
        if area == "software"
        else application.state.storage.paths.quarantine
    )
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(0o640)
    return fixture


def _url(item: DownloadFixture, *, filename: str | None = None) -> str:
    selected = item.display_filename if filename is None else filename
    return f"/download/{item.public_uuid}/{quote(selected, safe='')}"


def _extract_csrf(html: str) -> str:
    match = _CSRF_PATTERN.search(html)
    assert match is not None
    return match.group(1)


def _login_admin(application: FastAPI, client: TestClient) -> None:
    settings: AppSettings = application.state.settings
    AuthService(application.state.database, settings).create_admin(
        username="download-admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={
            "username": "download-admin",
            "password": "correct horse battery staple",
            "csrf_token": _extract_csrf(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    session_cookies = [
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{settings.session_cookie_name}=")
    ]
    assert len(session_cookies) == 1
    assert "Path=/;" in session_cookies[0]


def _counters(application: FastAPI, file_id: int) -> tuple[int, int, int, int]:
    with application.state.database.session() as session:
        release_file = session.get(ReleaseFile, file_id)
        stats = session.query(DownloadStat).filter_by(release_file_id=file_id).all()
        total = sum(item.download_count for item in stats)
        successful = sum(item.successful_download_count for item in stats)
        blocked = sum(item.blocked_download_count for item in stats)
        assert release_file is not None
        return release_file.download_count, total, successful, blocked


def test_get_and_head_return_internal_redirect_and_count_only_get(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_download_fixture(application, slug="public-download")

    head = client.head(_url(item))
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["x-accel-redirect"].startswith("/protected-downloads/")
    assert head.headers["content-length"] == "0"
    assert head.headers["content-type"] == "application/zip"
    assert head.headers["accept-ranges"] == "bytes"
    assert "filename*=UTF-8''" in head.headers["content-disposition"]
    assert _counters(application, item.file_id) == (0, 0, 0, 0)

    get = client.get(_url(item))
    assert get.status_code == 200
    assert get.content == b""
    assert get.headers["x-accel-redirect"].endswith(item.relative_path)
    assert get.headers["etag"].startswith('"sha256-')
    assert get.headers["cache-control"] == "no-store"
    assert _counters(application, item.file_id) == (1, 1, 1, 0)


def test_unlisted_file_is_available_by_direct_url(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_download_fixture(
        application,
        slug="unlisted-download",
        file_visibility=Visibility.UNLISTED,
        software_visibility=Visibility.UNLISTED,
    )

    assert client.get(_url(item)).status_code == 200
    assert _counters(application, item.file_id) == (1, 1, 1, 0)


def test_private_file_requires_root_scoped_admin_session(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_download_fixture(
        application,
        slug="private-download",
        file_visibility=Visibility.PRIVATE,
    )

    denied = client.get(_url(item), headers={"accept": "application/json"})
    assert denied.status_code == 404
    assert _counters(application, item.file_id) == (0, 0, 0, 1)

    _login_admin(application, client)
    allowed = client.get(_url(item))
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "private, no-store"
    assert _counters(application, item.file_id) == (1, 1, 1, 1)


@pytest.mark.parametrize(
    ("file_status", "release_status", "software_status"),
    [
        (FileStatus.DISABLED, ReleaseStatus.PUBLISHED, SoftwareStatus.PUBLISHED),
        (FileStatus.ARCHIVED, ReleaseStatus.PUBLISHED, SoftwareStatus.PUBLISHED),
        (FileStatus.PUBLISHED, ReleaseStatus.DRAFT, SoftwareStatus.PUBLISHED),
        (FileStatus.PUBLISHED, ReleaseStatus.DISABLED, SoftwareStatus.PUBLISHED),
        (FileStatus.PUBLISHED, ReleaseStatus.PUBLISHED, SoftwareStatus.HIDDEN),
        (FileStatus.PUBLISHED, ReleaseStatus.PUBLISHED, SoftwareStatus.DISABLED),
    ],
)
def test_ineligible_metadata_chain_returns_non_enumerating_404(
    application: FastAPI,
    client: TestClient,
    file_status: FileStatus,
    release_status: ReleaseStatus,
    software_status: SoftwareStatus,
) -> None:
    item = _create_download_fixture(
        application,
        slug=f"denied-{file_status}-{release_status}-{software_status}",
        file_status=file_status,
        release_status=release_status,
        software_status=software_status,
    )

    response = client.get(_url(item), headers={"accept": "application/json"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert _counters(application, item.file_id) == (0, 0, 0, 1)


def test_wrong_filename_is_blocked_without_authorized_count(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_download_fixture(application, slug="wrong-name")

    response = client.get(_url(item, filename="other.zip"))
    assert response.status_code == 404
    assert _counters(application, item.file_id) == (0, 0, 0, 1)


def test_missing_quarantine_and_size_mismatch_files_are_denied(
    application: FastAPI,
    client: TestClient,
) -> None:
    missing = _create_download_fixture(application, slug="missing-download")
    (application.state.storage.paths.software / missing.relative_path).unlink()

    quarantine = _create_download_fixture(
        application,
        slug="quarantine-location",
        area="quarantine",
    )

    mismatched = _create_download_fixture(
        application,
        slug="size-mismatch",
        payload=b"different-size",
    )
    with application.state.database.transaction() as session:
        record = session.get(ReleaseFile, mismatched.file_id)
        assert record is not None
        record.file_size_bytes += 1

    for item in (missing, quarantine, mismatched):
        assert client.get(_url(item)).status_code == 404
        assert _counters(application, item.file_id) == (0, 0, 0, 0)


def test_unknown_uuid_and_direct_internal_uri_are_not_available(client: TestClient) -> None:
    assert client.get(f"/download/{uuid4()}/missing.zip").status_code == 404
    assert client.get("/protected-downloads/aa/bb/file.zip").status_code == 404


def test_head_does_not_count_blocked_private_attempt(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_download_fixture(
        application,
        slug="private-head",
        file_visibility=Visibility.PRIVATE,
    )

    assert client.head(_url(item)).status_code == 404
    assert _counters(application, item.file_id) == (0, 0, 0, 1)


def test_download_stats_use_utc_calendar_date(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_download_fixture(application, slug="utc-date")
    assert client.get(_url(item)).status_code == 200

    with application.state.database.session() as session:
        stat = session.query(DownloadStat).filter_by(release_file_id=item.file_id).one()
    assert stat.date == datetime.now(UTC).date()
