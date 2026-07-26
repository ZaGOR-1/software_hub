"""Upload service integration tests across filesystem, scanner and SQLite."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import NoReturn

import pytest
from app.core.exceptions import StorageError, ValidationError
from app.models import Release, ReleaseFile, Software
from app.models.enums import (
    Architecture,
    FileStatus,
    PackageType,
    ScannerStatus,
    Visibility,
)
from app.services.upload_service import UploadMetadata, UploadService
from app.storage.manager import StorageManager
from app.storage.scanner import FileScanner, ScanResult
from fastapi import FastAPI
from sqlalchemy import select
from starlette.datastructures import Headers, UploadFile
from tests.async_utils import run_coroutine


@pytest.fixture(autouse=True)
def _initialize_storage(application: FastAPI) -> None:
    application.state.storage.initialize()


class FakeScanner:
    def __init__(self, status: ScannerStatus) -> None:
        self.status = status

    def scan(self, path: Path) -> ScanResult:
        assert path.is_file()
        return ScanResult(self.status, f"scanner={self.status.value}")


def _upload(
    filename: str,
    body: bytes,
    content_type: str = "application/octet-stream",
) -> UploadFile:
    return UploadFile(
        BytesIO(body),
        size=len(body),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _release_id(application: FastAPI) -> int:
    with application.state.database.transaction() as session:
        software = Software(
            name="Upload Tool",
            slug="upload-tool",
            short_description="Upload integration fixture",
        )
        release = Release(software=software, version="1.0.0")
        session.add(software)
        session.flush()
        return release.id


def _metadata(
    *,
    display_filename: str | None = None,
    source_url: str | None = "https://example.com/download",
) -> UploadMetadata:
    return UploadMetadata(
        display_filename=display_filename,
        architecture=Architecture.X64,
        package_type=PackageType.ARCHIVE,
        platform="Windows",
        edition=None,
        visibility=Visibility.PRIVATE,
        source_url=source_url,
        admin_note="manual review",
    )


def _run_upload(
    service: UploadService,
    *,
    release_id: int,
    upload: UploadFile,
    metadata: UploadMetadata,
    storage: StorageManager,
    scanner: FileScanner,
) -> ReleaseFile:
    async def run() -> ReleaseFile:
        return await service.upload_release_file(
            release_id=release_id,
            upload=upload,
            metadata=metadata,
            storage=storage,
            scanner=scanner,
        )

    return run_coroutine(run())


def test_valid_upload_moves_to_quarantine_and_persists_metadata(
    application: FastAPI,
) -> None:
    storage = application.state.storage
    release_id = _release_id(application)
    body = b"PK\x03\x04" + b"payload"
    service = UploadService(application.state.database, application.state.settings)

    release_file = _run_upload(
        service,
        release_id=release_id,
        upload=_upload("tool.zip", body, "text/plain"),
        metadata=_metadata(display_filename="Tool x64.zip"),
        storage=storage,
        scanner=FakeScanner(ScannerStatus.CLEAN),
    )

    assert release_file.status is FileStatus.READY
    assert release_file.scanner_status is ScannerStatus.CLEAN
    assert release_file.detected_mime_type == "application/zip"
    assert release_file.display_filename == "Tool x64.zip"
    assert release_file.sha256 == sha256(body).hexdigest()
    physical = storage.paths.quarantine / release_file.relative_storage_path
    assert physical.read_bytes() == body
    assert not any(storage.paths.temporary.iterdir())


def test_unknown_signature_and_scanner_error_remain_in_quarantine(
    application: FastAPI,
) -> None:
    storage = application.state.storage
    release_id = _release_id(application)
    service = UploadService(application.state.database, application.state.settings)

    release_file = _run_upload(
        service,
        release_id=release_id,
        upload=_upload("tool.zip", b"unknown-format"),
        metadata=_metadata(),
        storage=storage,
        scanner=FakeScanner(ScannerStatus.ERROR),
    )
    assert release_file.status is FileStatus.QUARANTINE
    assert release_file.detected_mime_type == "application/octet-stream"


def test_infected_upload_is_rejected_but_retained_for_review(
    application: FastAPI,
) -> None:
    storage = application.state.storage
    release_id = _release_id(application)
    service = UploadService(application.state.database, application.state.settings)

    release_file = _run_upload(
        service,
        release_id=release_id,
        upload=_upload("infected.zip", b"PK\x03\x04virus"),
        metadata=_metadata(),
        storage=storage,
        scanner=FakeScanner(ScannerStatus.INFECTED),
    )
    assert release_file.status is FileStatus.REJECTED
    assert (storage.paths.quarantine / release_file.relative_storage_path).exists()


def test_duplicate_hash_is_queryable_and_audited(application: FastAPI) -> None:
    storage = application.state.storage
    release_id = _release_id(application)
    service = UploadService(application.state.database, application.state.settings)
    body = b"PK\x03\x04same"

    first = _run_upload(
        service,
        release_id=release_id,
        upload=_upload("first.zip", body),
        metadata=_metadata(),
        storage=storage,
        scanner=FakeScanner(ScannerStatus.UNAVAILABLE),
    )
    second = _run_upload(
        service,
        release_id=release_id,
        upload=_upload("second.zip", body),
        metadata=_metadata(),
        storage=storage,
        scanner=FakeScanner(ScannerStatus.UNAVAILABLE),
    )
    assert first.sha256 == second.sha256
    with service.database.session() as session:
        records = list(
            session.scalars(select(ReleaseFile).where(ReleaseFile.sha256 == first.sha256))
        )
        assert len(records) == 2


def test_invalid_metadata_compensates_quarantine_file(application: FastAPI) -> None:
    storage = application.state.storage
    release_id = _release_id(application)
    service = UploadService(application.state.database, application.state.settings)

    with pytest.raises(ValidationError, match="URL"):
        _run_upload(
            service,
            release_id=release_id,
            upload=_upload("tool.zip", b"PK\x03\x04payload"),
            metadata=_metadata(source_url="file:///etc/passwd"),
            storage=storage,
            scanner=FakeScanner(ScannerStatus.CLEAN),
        )

    assert not list(storage.paths.temporary.rglob("*.upload"))
    assert not list(storage.paths.quarantine.rglob("*.zip"))
    with application.state.database.session() as session:
        assert session.scalar(select(ReleaseFile)) is None


def test_unexpected_metadata_failure_is_wrapped_and_compensated(
    application: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = application.state.storage
    release_id = _release_id(application)
    service = UploadService(application.state.database, application.state.settings)

    def fail_metadata(**_kwargs: object) -> NoReturn:
        raise RuntimeError("database boundary failed")

    monkeypatch.setattr(service, "_persist_metadata", fail_metadata)

    with pytest.raises(StorageError, match="completed safely"):
        _run_upload(
            service,
            release_id=release_id,
            upload=_upload("tool.zip", b"PK\x03\x04payload"),
            metadata=_metadata(),
            storage=storage,
            scanner=FakeScanner(ScannerStatus.CLEAN),
        )
    assert not list(storage.paths.quarantine.rglob("*.zip"))
