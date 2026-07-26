"""Physical and metadata lifecycle integration tests for Phase 11."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest
from app.core.exceptions import FileValidationError, InvalidStateTransition, StorageError
from app.models import AuditLog, Release, ReleaseFile, Software
from app.models.enums import (
    FileStatus,
    ReleaseStatus,
    ScannerStatus,
    SoftwareStatus,
    Visibility,
)
from app.services.file_service import FileService
from app.storage.filename import sharded_relative_path
from app.storage.lifecycle import StorageArea, locate_stored_file
from app.storage.paths import ensure_private_parent
from fastapi import FastAPI
from sqlalchemy import select

_BODY = b"PK\x03\x04phase-11-lifecycle"


def _create_file(
    application: FastAPI,
    *,
    status: FileStatus = FileStatus.READY,
    software_status: SoftwareStatus = SoftwareStatus.PUBLISHED,
    release_status: ReleaseStatus = ReleaseStatus.PUBLISHED,
    scanner_status: ScannerStatus = ScannerStatus.UNAVAILABLE,
    identifier: str = "a" * 32,
) -> int:
    storage = application.state.storage
    storage.initialize()
    storage_filename = f"{identifier}.zip"
    relative = sharded_relative_path(storage_filename)
    ensure_private_parent(storage.paths.quarantine, relative)
    path = storage.paths.quarantine / Path(*relative.parts)
    path.write_bytes(_BODY)
    path.chmod(0o640)

    with application.state.database.transaction() as session:
        software = Software(
            name=f"Lifecycle {identifier[:4]}",
            slug=f"lifecycle-{identifier[:4]}",
            short_description="Lifecycle test",
            status=software_status,
            visibility=Visibility.PUBLIC,
        )
        release = Release(
            software=software,
            version="1.0",
            status=release_status,
        )
        release_file = ReleaseFile(
            release=release,
            original_filename="tool.zip",
            display_filename="tool.zip",
            storage_filename=storage_filename,
            relative_storage_path=relative.as_posix(),
            file_extension=".zip",
            detected_mime_type="application/zip",
            file_size_bytes=len(_BODY),
            sha256=sha256(_BODY).hexdigest(),
            platform="Windows",
            status=status,
            visibility=Visibility.PRIVATE,
            scanner_status=scanner_status,
        )
        session.add(software)
        session.flush()
        return release_file.id


def _row(application: FastAPI, file_id: int) -> ReleaseFile | None:
    with application.state.database.session() as session:
        return cast(ReleaseFile | None, session.get(ReleaseFile, file_id))


def test_publish_moves_ready_file_and_updates_metadata(application: FastAPI) -> None:
    file_id = _create_file(application)
    service = FileService(application.state.database)

    published = service.publish(file_id, application.state.storage)

    assert published.status is FileStatus.PUBLISHED
    stored = locate_stored_file(
        application.state.storage.paths,
        published.relative_storage_path,
    )
    assert stored.area is StorageArea.SOFTWARE
    assert stored.path.read_bytes() == _BODY


def test_publish_rechecks_parent_state_and_checksum(application: FastAPI) -> None:
    file_id = _create_file(
        application,
        software_status=SoftwareStatus.DRAFT,
        identifier="b" * 32,
    )
    service = FileService(application.state.database)
    with pytest.raises(InvalidStateTransition):
        service.publish(file_id, application.state.storage)
    assert (
        locate_stored_file(
            application.state.storage.paths,
            service.get(file_id).relative_storage_path,
        ).area
        is StorageArea.QUARANTINE
    )

    valid_id = _create_file(application, identifier="c" * 32)
    record = service.get(valid_id)
    stored = locate_stored_file(application.state.storage.paths, record.relative_storage_path)
    stored.path.write_bytes(b"PK\x03\x04tampered")
    with pytest.raises(FileValidationError):
        service.publish(valid_id, application.state.storage)
    assert service.get(valid_id).status is FileStatus.READY


def test_publish_database_failure_restores_quarantine(
    application: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = _create_file(application, identifier="d" * 32)

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced transaction failure")

    monkeypatch.setattr("app.services.file_service.append_context_audit_event", fail_audit)
    with pytest.raises(StorageError):
        FileService(application.state.database).publish(file_id, application.state.storage)

    record = FileService(application.state.database).get(file_id)
    assert record.status is FileStatus.READY
    assert (
        locate_stored_file(
            application.state.storage.paths,
            record.relative_storage_path,
        ).area
        is StorageArea.QUARANTINE
    )


def test_disable_restore_and_archive_preserve_bytes(application: FastAPI) -> None:
    file_id = _create_file(application, identifier="e" * 32)
    service = FileService(application.state.database)
    service.publish(file_id, application.state.storage)

    disabled = service.disable(file_id, application.state.storage)
    assert disabled.status is FileStatus.DISABLED
    assert (
        locate_stored_file(
            application.state.storage.paths,
            disabled.relative_storage_path,
        ).area
        is StorageArea.SOFTWARE
    )

    restored = service.restore_ready(file_id, application.state.storage)
    assert restored.status is FileStatus.READY
    assert (
        locate_stored_file(
            application.state.storage.paths,
            restored.relative_storage_path,
        ).area
        is StorageArea.QUARANTINE
    )

    archived = service.archive(file_id, application.state.storage)
    assert archived.status is FileStatus.ARCHIVED
    assert (
        locate_stored_file(
            application.state.storage.paths,
            archived.relative_storage_path,
        ).path.read_bytes()
        == _BODY
    )


def test_metadata_only_delete_preserves_orphan(application: FastAPI) -> None:
    file_id = _create_file(application, identifier="f" * 32)
    service = FileService(application.state.database)
    relative = service.get(file_id).relative_storage_path

    result = service.delete_metadata(file_id, application.state.storage)

    assert result.physical_file_preserved is True
    assert result.storage_area is StorageArea.QUARANTINE
    assert _row(application, file_id) is None
    assert locate_stored_file(application.state.storage.paths, relative).path.exists()


def test_permanent_delete_removes_metadata_and_bytes(application: FastAPI) -> None:
    file_id = _create_file(application, identifier="1" * 32)
    service = FileService(application.state.database)
    relative = service.get(file_id).relative_storage_path

    result = service.permanently_delete(file_id, application.state.storage)

    assert result.physical_file_preserved is False
    assert _row(application, file_id) is None
    assert not (application.state.storage.paths.quarantine / Path(*Path(relative).parts)).exists()
    assert not list((application.state.storage.paths.temporary / "deletions").glob("*.delete"))


def test_permanent_delete_database_failure_restores_file(
    application: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = _create_file(application, identifier="2" * 32)
    service = FileService(application.state.database)
    relative = service.get(file_id).relative_storage_path

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced transaction failure")

    monkeypatch.setattr("app.services.file_service.append_context_audit_event", fail_audit)
    with pytest.raises(StorageError):
        service.permanently_delete(file_id, application.state.storage)

    assert _row(application, file_id) is not None
    assert locate_stored_file(application.state.storage.paths, relative).path.read_bytes() == _BODY


def test_published_file_requires_disable_before_delete(application: FastAPI) -> None:
    file_id = _create_file(application, identifier="3" * 32)
    service = FileService(application.state.database)
    service.publish(file_id, application.state.storage)

    with pytest.raises(InvalidStateTransition):
        service.delete_metadata(file_id, application.state.storage)
    with pytest.raises(InvalidStateTransition):
        service.permanently_delete(file_id, application.state.storage)


def test_integrity_verification_writes_audit_when_context_exists(application: FastAPI) -> None:
    from app.services.audit_service import AuditContext
    from app.services.auth_service import AuthService

    admin = AuthService(application.state.database, application.state.settings).create_admin(
        username="lifecycle-admin",
        password="correct horse battery staple",
    )
    file_id = _create_file(application, identifier="4" * 32)
    FileService(application.state.database).verify_integrity(
        file_id,
        application.state.storage,
        audit=AuditContext(user_id=admin.id, request_id="phase11"),
    )

    with application.state.database.session() as session:
        action = session.scalar(select(AuditLog.action).where(AuditLog.action == "file_verified"))
    assert action == "file_verified"


def test_infected_file_cannot_be_approved(application: FastAPI) -> None:
    file_id = _create_file(
        application,
        status=FileStatus.QUARANTINE,
        scanner_status=ScannerStatus.INFECTED,
        identifier="5" * 32,
    )
    with pytest.raises(InvalidStateTransition):
        FileService(application.state.database).review_status(
            file_id,
            FileStatus.READY,
            application.state.storage,
        )
    assert FileService(application.state.database).get(file_id).status is FileStatus.QUARANTINE


def test_duplicate_physical_locations_fail_closed(application: FastAPI) -> None:
    file_id = _create_file(application, identifier="6" * 32)
    service = FileService(application.state.database)
    record = service.get(file_id)
    relative = Path(record.relative_storage_path)
    duplicate = application.state.storage.paths.software / relative
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    duplicate.write_bytes(_BODY)
    duplicate.chmod(0o640)

    with pytest.raises(StorageError):
        service.storage_state(file_id, application.state.storage)
    with pytest.raises(StorageError):
        service.publish(file_id, application.state.storage)


def test_permanent_delete_from_software_after_disable(application: FastAPI) -> None:
    file_id = _create_file(application, identifier="7" * 32)
    service = FileService(application.state.database)
    published = service.publish(file_id, application.state.storage)
    service.disable(file_id, application.state.storage)
    relative = published.relative_storage_path

    service.permanently_delete(file_id, application.state.storage)

    assert _row(application, file_id) is None
    assert not (application.state.storage.paths.software / Path(relative)).exists()


def test_final_unlink_failure_leaves_private_staged_artifact(
    application: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = _create_file(application, identifier="8" * 32)

    def fail_unlink(*_args: object, **_kwargs: object) -> None:
        raise StorageError("forced final unlink failure")

    monkeypatch.setattr("app.services.file_service.unlink_staged_deletion", fail_unlink)
    with pytest.raises(StorageError, match="operator attention"):
        FileService(application.state.database).permanently_delete(
            file_id,
            application.state.storage,
        )

    assert _row(application, file_id) is None
    staged = list((application.state.storage.paths.temporary / "deletions").glob("*.delete"))
    assert len(staged) == 1
    assert staged[0].read_bytes() == _BODY
