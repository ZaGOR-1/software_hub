"""Storage reconciliation, orphan cleanup and checksum maintenance tests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.core.config import AppSettings
from app.database.session import Database
from app.models.enums import FileStatus
from app.models.release_file import ReleaseFile
from app.services.reconciliation_service import (
    ReconciliationIssueKind,
    ReconciliationService,
)
from app.storage.filename import sharded_relative_path
from app.storage.manager import StorageManager
from app.storage.paths import ensure_private_parent
from tests.fixtures.models import make_catalog_graph

_BODY = b"PK\x03\x04phase-16-reconciliation"


def _persist_file(
    database: Database,
    storage: StorageManager,
    *,
    status: FileStatus = FileStatus.PUBLISHED,
) -> int:
    storage.initialize()
    with database.transaction() as session:
        release_file = make_catalog_graph(session, slug="phase16")
        relative = sharded_relative_path("f" * 32 + ".zip")
        release_file.relative_storage_path = relative.as_posix()
        release_file.storage_filename = "f" * 32 + ".zip"
        release_file.file_extension = ".zip"
        release_file.file_size_bytes = len(_BODY)
        release_file.sha256 = sha256(_BODY).hexdigest()
        release_file.status = status
        session.flush()
        file_id = release_file.id
    root = storage.paths.software if status is FileStatus.PUBLISHED else storage.paths.quarantine
    ensure_private_parent(root, relative)
    path = root / Path(*relative.parts)
    path.write_bytes(_BODY)
    path.chmod(0o640)
    return file_id


def test_verify_storage_healthy(domain_database: Database, test_settings: AppSettings) -> None:
    settings = test_settings
    storage = StorageManager.from_settings(settings)
    _persist_file(domain_database, storage)

    report = ReconciliationService(domain_database, storage).verify_storage()

    assert report.healthy is True
    assert report.metadata_count == 1
    assert report.physical_file_count == 1
    assert report.verified_count == 1


def test_detects_missing_duplicate_area_size_checksum_and_orphans(
    domain_database: Database,
    test_settings: AppSettings,
) -> None:
    settings = test_settings
    storage = StorageManager.from_settings(settings)
    file_id = _persist_file(domain_database, storage)
    with domain_database.session() as session:
        entity = session.get(ReleaseFile, file_id)
        assert entity is not None
        relative = entity.relative_storage_path
    software_file = storage.paths.software / Path(*Path(relative).parts)
    quarantine_file = storage.paths.quarantine / Path(*Path(relative).parts)
    ensure_private_parent(storage.paths.quarantine, relative)
    quarantine_file.write_bytes(b"duplicate-and-tampered")
    orphan = storage.paths.software / "orphan.bin"
    orphan.write_bytes(b"orphan")

    report = ReconciliationService(domain_database, storage).verify_storage()
    kinds = {issue.kind for issue in report.issues}
    assert ReconciliationIssueKind.DUPLICATE_STORAGE_LOCATION in kinds
    assert ReconciliationIssueKind.ORPHAN_FILE in kinds

    quarantine_file.unlink()
    software_file.write_bytes(b"tampered")
    report = ReconciliationService(domain_database, storage).verify_storage()
    kinds = {issue.kind for issue in report.issues}
    assert ReconciliationIssueKind.SIZE_MISMATCH in kinds
    assert ReconciliationIssueKind.CHECKSUM_MISMATCH in kinds

    software_file.unlink()
    report = ReconciliationService(domain_database, storage).verify_storage()
    assert ReconciliationIssueKind.METADATA_WITHOUT_FILE in {issue.kind for issue in report.issues}


def test_orphan_cleanup_is_dry_run_then_explicit(
    domain_database: Database,
    test_settings: AppSettings,
) -> None:
    settings = test_settings
    storage = StorageManager.from_settings(settings)
    storage.initialize()
    orphan = storage.paths.quarantine / "orphan.zip"
    orphan.write_bytes(b"orphan")

    service = ReconciliationService(domain_database, storage)
    dry_run = service.cleanup_orphans(dry_run=True)
    assert len(dry_run.discovered) == 1
    assert dry_run.deleted_count == 0
    assert orphan.exists()

    applied = service.cleanup_orphans(dry_run=False)
    assert applied.deleted_count == 1
    assert applied.errors == 0
    assert not orphan.exists()


def test_recalculate_is_dry_run_and_protects_published_files(
    domain_database: Database,
    test_settings: AppSettings,
) -> None:
    settings = test_settings
    storage = StorageManager.from_settings(settings)
    file_id = _persist_file(domain_database, storage, status=FileStatus.PUBLISHED)
    with domain_database.session() as session:
        entity = session.get(ReleaseFile, file_id)
        assert entity is not None
        path = storage.paths.software / Path(*Path(entity.relative_storage_path).parts)
    path.write_bytes(b"new physical bytes")

    service = ReconciliationService(domain_database, storage)
    protected = service.recalculate_checksums(dry_run=False, include_published=False)
    assert protected.skipped_published_count == 1
    assert protected.updated_count == 0

    dry_run = service.recalculate_checksums(dry_run=True, include_published=True)
    assert len(dry_run.changes) == 1
    assert dry_run.updated_count == 0

    applied = service.recalculate_checksums(dry_run=False, include_published=True)
    assert applied.updated_count == 1
    with domain_database.session() as session:
        updated = session.get(ReleaseFile, file_id)
        assert updated is not None
        assert updated.sha256 == sha256(b"new physical bytes").hexdigest()
        assert updated.file_size_bytes == len(b"new physical bytes")


def test_wrong_area_and_skip_checksum_mode(
    domain_database: Database,
    test_settings: AppSettings,
) -> None:
    storage = StorageManager.from_settings(test_settings)
    file_id = _persist_file(
        domain_database,
        storage,
        status=FileStatus.QUARANTINE,
    )
    with domain_database.session() as session:
        entity = session.get(ReleaseFile, file_id)
        assert entity is not None
        relative = entity.relative_storage_path
    source = storage.paths.quarantine / Path(*Path(relative).parts)
    target = storage.paths.software / Path(*Path(relative).parts)
    ensure_private_parent(storage.paths.software, relative)
    source.replace(target)
    target.write_bytes(b"changed but same verification is skipped")

    report = ReconciliationService(domain_database, storage).verify_storage(verify_checksums=False)
    kinds = {issue.kind for issue in report.issues}
    assert ReconciliationIssueKind.UNEXPECTED_STORAGE_AREA in kinds
    assert ReconciliationIssueKind.SIZE_MISMATCH in kinds
    assert ReconciliationIssueKind.CHECKSUM_MISMATCH not in kinds
