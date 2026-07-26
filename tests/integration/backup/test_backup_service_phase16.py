"""Verified backup, retention and restore integration tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from app.core.config import AppSettings
from app.core.exceptions import StorageError, ValidationError
from app.database.migrations_helpers import upgrade_database
from app.database.session import create_database
from app.models import AuditLog, Category
from app.services.backup_service import BackupService
from app.storage.manager import StorageManager
from sqlalchemy import select


def _standalone_settings(test_settings: AppSettings) -> AppSettings:
    return test_settings.model_copy(
        update={
            "backup_min_free_bytes": 0,
            "backup_retention_count": 2,
        }
    )


def _prepare(settings: AppSettings) -> StorageManager:
    upgrade_database(settings.database_url)
    storage = StorageManager.from_settings(settings)
    storage.initialize()
    database = create_database(settings)
    try:
        with database.transaction() as session:
            session.add(Category(name="Utilities", slug="utilities"))
    finally:
        database.dispose()
    file_path = storage.paths.software / "aa" / "bb" / "fixture.zip"
    file_path.parent.mkdir(mode=0o750, parents=True)
    file_path.write_bytes(b"PK\x03\x04phase-16-backup")
    file_path.chmod(0o640)
    temporary = storage.paths.temporary / ("0" * 32 + ".upload")
    temporary.write_bytes(b"not included")
    return storage


def test_create_and_verify_backup_with_manifest(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)

    created = service.create_backup()
    verified = service.verify_backup(created.backup_id)
    backup = settings.backup_root / created.backup_id

    assert created.file_count >= 5
    assert created.total_bytes > 0
    assert verified.checksum_verified is True
    assert verified.database_integrity_verified is True
    assert verified.database_revision == "0002_phase4_domain_schema"
    assert (backup / "manifest.json").is_file()
    assert (backup / "manifest.sha256").is_file()
    assert (backup / "database" / "software-hub.sqlite3").is_file()
    assert (backup / "storage" / "software" / "aa" / "bb" / "fixture.zip").is_file()
    assert not (backup / "storage" / "temporary").exists()
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["backup_id"] == created.backup_id
    assert manifest["file_count"] == created.file_count
    assert manifest["database_revision"] == "0002_phase4_domain_schema"


def test_verify_detects_tampering_and_undeclared_files(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)
    created = service.create_backup()
    backup = settings.backup_root / created.backup_id

    database_copy = backup / "database" / "software-hub.sqlite3"
    database_copy.write_bytes(database_copy.read_bytes() + b"tamper")
    with pytest.raises(ValidationError, match=r"size|checksum"):
        service.verify_backup(created.backup_id)

    shutil_target = settings.backup_root / created.backup_id
    shutil_target.rename(settings.backup_root / f"{created.backup_id}.broken")
    created = service.create_backup()
    extra = settings.backup_root / created.backup_id / "undeclared.bin"
    extra.write_bytes(b"extra")
    with pytest.raises(ValidationError, match="not declared"):
        service.verify_backup(created.backup_id)


def test_retention_is_dry_run_by_default_and_keeps_newest(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)
    first = service.create_backup(apply_retention=False)
    second = service.create_backup(apply_retention=False)
    third = service.create_backup(apply_retention=False)

    dry_run = service.apply_retention(dry_run=True)
    assert dry_run.eligible == (first.backup_id,)
    assert (settings.backup_root / first.backup_id).exists()

    applied = service.apply_retention(dry_run=False)
    assert applied.deleted == (first.backup_id,)
    assert not (settings.backup_root / first.backup_id).exists()
    assert (settings.backup_root / second.backup_id).exists()
    assert (settings.backup_root / third.backup_id).exists()


def test_restore_replaces_database_and_storage(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    storage = _prepare(settings)
    service = BackupService(settings)
    created = service.create_backup(apply_retention=False)

    database = create_database(settings)
    try:
        with database.transaction() as session:
            category = session.scalar(select(Category).where(Category.slug == "utilities"))
            assert category is not None
            category.name = "Mutated"
            session.add(Category(name="Other", slug="other"))
    finally:
        database.dispose()
    stored_file = storage.paths.software / "aa" / "bb" / "fixture.zip"
    stored_file.unlink()
    orphan = storage.paths.software / "orphan.bin"
    orphan.write_bytes(b"orphan")

    restored = service.restore_backup(created.backup_id, create_safety_backup=False)

    assert restored.backup_id == created.backup_id
    assert restored.pre_restore_backup_id is None
    database = create_database(settings)
    try:
        with database.session() as session:
            categories = list(session.scalars(select(Category).order_by(Category.slug)))
            assert [(item.slug, item.name) for item in categories] == [("utilities", "Utilities")]
    finally:
        database.dispose()
    assert stored_file.read_bytes() == b"PK\x03\x04phase-16-backup"
    assert not orphan.exists()
    assert settings.temporary_root.is_dir()


def test_operation_lock_and_interrupted_backup_cleanup(
    test_settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)
    lock = settings.backup_root / ".software-hub-backup.lock"
    lock.write_text("occupied", encoding="ascii")
    with pytest.raises(StorageError, match="already running"):
        service.create_backup()
    lock.unlink()

    def fail_copy(_destination: Path) -> list[object]:
        raise StorageError("forced copy failure")

    monkeypatch.setattr(service, "_copy_storage", fail_copy)
    with pytest.raises(StorageError, match="forced copy failure"):
        service.create_backup()
    assert not list(settings.backup_root.glob(".*.tmp-*"))


def test_restore_creates_safety_backup(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)
    selected = service.create_backup(apply_retention=False)

    report = service.restore_backup(selected.backup_id)

    assert report.pre_restore_backup_id is not None
    assert report.pre_restore_backup_id != selected.backup_id
    assert service.verify_backup(report.pre_restore_backup_id).checksum_verified is True


def test_restore_failure_compensates_live_state(
    test_settings: AppSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _standalone_settings(test_settings)
    storage = _prepare(settings)
    service = BackupService(settings)
    selected = service.create_backup(apply_retention=False)

    database = create_database(settings)
    try:
        with database.transaction() as session:
            category = session.scalar(select(Category).where(Category.slug == "utilities"))
            assert category is not None
            category.name = "Live state"
    finally:
        database.dispose()
    live_file = storage.paths.software / "live-after-backup.bin"
    live_file.write_bytes(b"live")

    def fail_migration(_database_url: str) -> None:
        raise RuntimeError("forced migration failure")

    monkeypatch.setattr("app.services.backup_service.upgrade_database", fail_migration)
    with pytest.raises(RuntimeError, match="forced migration"):
        service.restore_backup(selected.backup_id, create_safety_backup=False)

    database = create_database(settings)
    try:
        with database.session() as session:
            category = session.scalar(select(Category).where(Category.slug == "utilities"))
            assert category is not None
            assert category.name == "Live state"
    finally:
        database.dispose()
    assert live_file.read_bytes() == b"live"


def test_empty_storage_backup_can_be_restored(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    upgrade_database(settings.database_url)
    StorageManager.from_settings(settings).initialize()
    service = BackupService(settings)
    selected = service.create_backup(apply_retention=False)

    report = service.restore_backup(selected.backup_id, create_safety_backup=False)

    assert report.file_count >= 4
    assert settings.storage_root.is_dir()
    assert settings.temporary_root.is_dir()


def test_live_sqlite_backup_remains_consistent_during_short_writes(
    test_settings: AppSettings,
) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)
    stop = threading.Event()
    errors: list[Exception] = []

    def writer() -> None:
        database = create_database(settings)
        index = 0
        try:
            while not stop.is_set() and index < 50:
                try:
                    with database.transaction() as session:
                        session.add(
                            Category(
                                name=f"Live {index}",
                                slug=f"live-{index}",
                            )
                        )
                except Exception as exc:  # noqa: BLE001 - captured for assertion.
                    errors.append(exc)
                index += 1
        finally:
            database.dispose()

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        created = service.create_backup(apply_retention=False)
    finally:
        stop.set()
        thread.join(timeout=10)

    assert not errors
    assert service.verify_backup(created.backup_id).database_integrity_verified is True


def test_backup_and_restore_write_safe_audit_events(test_settings: AppSettings) -> None:
    settings = _standalone_settings(test_settings)
    _prepare(settings)
    service = BackupService(settings)
    created = service.create_backup(apply_retention=False)
    service.restore_backup(created.backup_id, create_safety_backup=False)

    database = create_database(settings)
    try:
        with database.session() as session:
            actions = list(session.scalars(select(AuditLog.action).order_by(AuditLog.id)))
    finally:
        database.dispose()
    assert "backup_restored" in actions
