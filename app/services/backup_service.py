"""Verified directory backups and fail-safe restore operations."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final
from uuid import uuid4

from sqlalchemy.engine import make_url

from app import __version__
from app.core.config import AppSettings
from app.core.exceptions import StorageError, ValidationError
from app.core.time import utc_now
from app.database.migrations_helpers import upgrade_database
from app.database.session import create_database
from app.services.audit_service import (
    AuditAction,
    AuditResult,
    append_audit_event,
)
from app.storage.disk import ensure_free_space
from app.storage.hashing import sha256_file
from app.storage.manager import StorageManager
from app.storage.paths import ensure_private_directory

logger = logging.getLogger(__name__)

_BACKUP_PREFIX: Final[str] = "software-hub-backup-"
_MANIFEST_NAME: Final[str] = "manifest.json"
_MANIFEST_CHECKSUM_NAME: Final[str] = "manifest.sha256"
_LOCK_NAME: Final[str] = ".software-hub-backup.lock"
_BACKUP_ID_PATTERN = re.compile(r"^software-hub-backup-\d{8}T\d{6}\d{6}Z-[0-9a-f]{8}$")
_REVISION_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_MAX_MANIFEST_BYTES: Final[int] = 4 * 1024 * 1024
_COPY_CHUNK_SIZE: Final[int] = 1024 * 1024
_MANIFEST_VERSION: Final[int] = 1


@dataclass(frozen=True, slots=True)
class BackupEntry:
    """One regular file protected by the backup manifest."""

    relative_path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """Versioned and deterministic backup metadata."""

    backup_id: str
    created_at: datetime
    app_version: str
    database_revision: str
    entries: tuple[BackupEntry, ...]

    @property
    def total_bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": _MANIFEST_VERSION,
            "backup_id": self.backup_id,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "app_version": self.app_version,
            "database_revision": self.database_revision,
            "total_bytes": self.total_bytes,
            "file_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class BackupVerificationReport:
    """Result of complete manifest, content and SQLite verification."""

    backup_id: str
    created_at: datetime
    file_count: int
    total_bytes: int
    database_revision: str
    checksum_verified: bool
    database_integrity_verified: bool


@dataclass(frozen=True, slots=True)
class BackupCreationReport:
    """Completed backup and retention summary."""

    backup_id: str
    file_count: int
    total_bytes: int
    retention_deleted_count: int


@dataclass(frozen=True, slots=True)
class RetentionReport:
    """Dry-run or destructive retention result."""

    discovered: int
    eligible: tuple[str, ...]
    deleted: tuple[str, ...]
    errors: int
    dry_run: bool


@dataclass(frozen=True, slots=True)
class RestoreReport:
    """Verified restore result with the automatic safety-backup identifier."""

    backup_id: str
    pre_restore_backup_id: str | None
    file_count: int
    total_bytes: int


def _safe_relative_path(value: str) -> PurePosixPath:
    if not value or "\x00" in value or "\\" in value:
        raise ValidationError("Backup manifest contains an invalid path.")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValidationError("Backup manifest contains an invalid path.")
    return relative


def _safe_backup_id(value: str) -> str:
    candidate = value.strip()
    if not _BACKUP_ID_PATTERN.fullmatch(candidate):
        raise ValidationError("The backup identifier is invalid.")
    return candidate


def _regular_file(path: Path, *, message: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise StorageError(message) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise StorageError(message)
    return metadata


def _copy_regular_file(source: Path, destination: Path) -> BackupEntry:
    metadata = _regular_file(source, message="A backup source file is unavailable.")
    destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise StorageError("A backup destination unexpectedly already exists.")
    try:
        with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
            shutil.copyfileobj(source_stream, destination_stream, length=_COPY_CHUNK_SIZE)
            destination_stream.flush()
            os.fsync(destination_stream.fileno())
        destination.chmod(0o600)
    except OSError as exc:
        raise StorageError("A backup file could not be copied.") from exc
    digest, size = sha256_file(destination)
    final_metadata = _regular_file(source, message="A backup source file is unavailable.")
    if (
        size != metadata.st_size
        or final_metadata.st_size != metadata.st_size
        or final_metadata.st_mtime_ns != metadata.st_mtime_ns
    ):
        raise StorageError("A backup source changed while it was being copied.")
    return BackupEntry(
        relative_path=destination.as_posix(),
        size_bytes=size,
        sha256=digest,
    )


def _database_path(settings: AppSettings) -> Path:
    database_name = make_url(settings.database_url).database
    if database_name is None or database_name in {"", ":memory:"}:
        raise ValidationError("A persistent SQLite database is required for backup operations.")
    path = Path(database_name)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def _sqlite_integrity_check(path: Path) -> None:
    _regular_file(path, message="The backup database is unavailable.")
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise StorageError("The backup database could not be verified.") from exc
    if result is None or result[0] != "ok":
        raise ValidationError("SQLite integrity verification failed.")


def _sqlite_schema_revision(path: Path) -> str:
    _regular_file(path, message="The backup database is unavailable.")
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise StorageError("The backup database revision could not be read.") from exc
    if row is None or not _REVISION_PATTERN.fullmatch(str(row[0])):
        raise ValidationError("The backup database revision is invalid.")
    return str(row[0])


class BackupService:
    """Create, verify, retain and restore complete Software Hub backups."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.backup_root = settings.backup_root
        self.storage_root = settings.storage_root
        self.database_path = _database_path(settings)
        self.project_root = Path(__file__).resolve().parents[2]

    def create_backup(
        self,
        *,
        apply_retention: bool = True,
        audit: bool = True,
    ) -> BackupCreationReport:
        """Create a verified backup in a temporary directory, then publish atomically."""

        ensure_private_directory(self.backup_root)
        StorageManager.from_settings(self.settings).initialize()
        backup_id = self._new_backup_id()
        temporary = self.backup_root / f".{backup_id}.tmp-{uuid4().hex}"
        destination = self.backup_root / backup_id
        retention_deleted = 0
        try:
            with self._operation_lock():
                ensure_free_space(
                    self.backup_root,
                    required_bytes=self._estimate_source_bytes(),
                    reserve_bytes=self.settings.backup_min_free_bytes,
                )
                temporary.mkdir(mode=0o750)
                entries = self._populate_backup(temporary)
                manifest = BackupManifest(
                    backup_id=backup_id,
                    created_at=utc_now(),
                    app_version=__version__,
                    database_revision=_sqlite_schema_revision(
                        temporary / "database" / "software-hub.sqlite3"
                    ),
                    entries=tuple(sorted(entries, key=lambda entry: entry.relative_path)),
                )
                self._write_manifest(temporary, manifest)
                self._verify_directory(temporary, expected_backup_id=backup_id)
                temporary.replace(destination)
                self._fsync_directory(self.backup_root)
                if apply_retention:
                    retention = self.apply_retention(
                        dry_run=False,
                        protected_ids={backup_id},
                        acquire_lock=False,
                    )
                    retention_deleted = len(retention.deleted)
            report = BackupCreationReport(
                backup_id=backup_id,
                file_count=len(manifest.entries),
                total_bytes=manifest.total_bytes,
                retention_deleted_count=retention_deleted,
            )
            if audit:
                self._audit(
                    action=AuditAction.BACKUP_CREATED,
                    result=AuditResult.SUCCESS,
                    backup_id=backup_id,
                    metadata={
                        "backup_id": backup_id,
                        "file_count": report.file_count,
                        "total_bytes": report.total_bytes,
                        "retention_deleted_count": retention_deleted,
                        "checksum_verified": True,
                    },
                )
            return report  # noqa: TRY300 - success result precedes shared failure cleanup
        except Exception as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            if audit:
                self._audit(
                    action=AuditAction.BACKUP_FAILED,
                    result=AuditResult.FAILURE,
                    backup_id=backup_id,
                    metadata={"backup_id": backup_id, "reason": type(exc).__name__},
                )
            raise

    def verify_backup(self, backup_id: str) -> BackupVerificationReport:
        """Verify manifest checksum, every file checksum and SQLite integrity."""

        directory = self._backup_directory(backup_id)
        return self._verify_directory(directory, expected_backup_id=backup_id)

    def list_backups(self) -> tuple[BackupVerificationReport, ...]:
        """Return verified backups in newest-first order, ignoring invalid entries."""

        reports: list[BackupVerificationReport] = []
        for entry in self._recognized_backup_directories():
            try:
                reports.append(self._verify_directory(entry, expected_backup_id=entry.name))
            except StorageError, ValidationError:
                logger.warning("backup_inventory_entry_invalid")
        return tuple(sorted(reports, key=lambda report: report.created_at, reverse=True))

    def apply_retention(
        self,
        *,
        dry_run: bool = True,
        protected_ids: set[str] | None = None,
        acquire_lock: bool = True,
    ) -> RetentionReport:
        """Keep the newest configured number of valid backups."""

        context = self._operation_lock() if acquire_lock else _null_context()
        with context:
            reports = self.list_backups()
            protected = protected_ids or set()
            keep_count = self.settings.backup_retention_count
            eligible = tuple(
                report.backup_id
                for report in reports[keep_count:]
                if report.backup_id not in protected
            )
            deleted: list[str] = []
            errors = 0
            if not dry_run:
                for backup_id in eligible:
                    try:
                        shutil.rmtree(self._backup_directory(backup_id))
                        deleted.append(backup_id)
                    except OSError:
                        errors += 1
                self._fsync_directory(self.backup_root)
            return RetentionReport(
                discovered=len(reports),
                eligible=eligible,
                deleted=tuple(deleted),
                errors=errors,
                dry_run=dry_run,
            )

    def restore_backup(
        self,
        backup_id: str,
        *,
        create_safety_backup: bool = True,
    ) -> RestoreReport:
        """Restore a verified backup using staged same-filesystem replacements."""

        selected = _safe_backup_id(backup_id)
        verification = self.verify_backup(selected)
        safety_backup_id: str | None = None
        if create_safety_backup:
            safety_backup_id = self.create_backup(
                apply_retention=False,
                audit=False,
            ).backup_id
        with self._operation_lock():
            self._restore_verified_backup(selected)
        self._audit(
            action=AuditAction.BACKUP_RESTORED,
            result=AuditResult.SUCCESS,
            backup_id=selected,
            metadata={
                "backup_id": selected,
                "file_count": verification.file_count,
                "total_bytes": verification.total_bytes,
                "checksum_verified": True,
            },
        )
        return RestoreReport(
            backup_id=selected,
            pre_restore_backup_id=safety_backup_id,
            file_count=verification.file_count,
            total_bytes=verification.total_bytes,
        )

    def _populate_backup(self, destination: Path) -> list[BackupEntry]:
        entries: list[BackupEntry] = []
        database_destination = destination / "database" / "software-hub.sqlite3"
        self._backup_sqlite(database_destination)
        database_digest, database_size = sha256_file(database_destination)
        entries.append(
            BackupEntry(
                relative_path="database/software-hub.sqlite3",
                size_bytes=database_size,
                sha256=database_digest,
            )
        )
        entries.extend(self._copy_storage(destination / "storage"))
        entries.extend(self._copy_config_templates(destination / "config"))
        return entries

    def _backup_sqlite(self, destination: Path) -> None:
        _regular_file(self.database_path, message="The live SQLite database is unavailable.")
        destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        try:
            source = sqlite3.connect(
                f"file:{self.database_path.as_posix()}?mode=ro",
                uri=True,
            )
            target = sqlite3.connect(destination)
            try:
                source.backup(target, pages=256, sleep=0.01)
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                target.execute("PRAGMA journal_mode=DELETE")
                target.commit()
            finally:
                target.close()
                source.close()
            for suffix in ("-wal", "-shm"):
                Path(f"{destination}{suffix}").unlink(missing_ok=True)
            destination.chmod(0o600)
        except sqlite3.Error as exc:
            raise StorageError("The SQLite backup operation failed.") from exc
        _sqlite_integrity_check(destination)

    def _copy_storage(self, destination: Path) -> list[BackupEntry]:
        if self.storage_root.is_symlink() or not self.storage_root.is_dir():
            raise StorageError("Private storage is unavailable for backup.")
        destination.mkdir(mode=0o750, parents=True, exist_ok=False)
        temporary_relative = self.settings.temporary_root.relative_to(self.storage_root)
        entries: list[BackupEntry] = []
        for current, directory_names, file_names in self.storage_root.walk(follow_symlinks=False):
            relative_directory = current.relative_to(self.storage_root)
            symlink_directories = [
                name for name in directory_names if (current / name).is_symlink()
            ]
            if symlink_directories:
                raise StorageError("Private storage cannot contain symbolic links.")
            directory_names[:] = [
                name
                for name in directory_names
                if not self._excluded_storage_path(
                    relative_directory / name,
                    temporary_relative,
                )
            ]
            for name in file_names:
                relative = relative_directory / name
                if self._excluded_storage_path(relative, temporary_relative):
                    continue
                source = current / name
                target = destination / relative
                entry = _copy_regular_file(source, target)
                entries.append(
                    BackupEntry(
                        relative_path=f"storage/{relative.as_posix()}",
                        size_bytes=entry.size_bytes,
                        sha256=entry.sha256,
                    )
                )
        return entries

    @staticmethod
    def _excluded_storage_path(path: Path, temporary_relative: Path) -> bool:
        return path == temporary_relative or temporary_relative in path.parents

    def _copy_config_templates(self, destination: Path) -> list[BackupEntry]:
        candidates = (
            self.project_root / ".env.example",
            self.project_root / "alembic.ini",
            self.project_root / "pyproject.toml",
        )
        entries: list[BackupEntry] = []
        for source in candidates:
            if not source.is_file() or source.is_symlink():
                continue
            target = destination / source.name
            entry = _copy_regular_file(source, target)
            entries.append(
                BackupEntry(
                    relative_path=f"config/{source.name}",
                    size_bytes=entry.size_bytes,
                    sha256=entry.sha256,
                )
            )
        nginx = self.project_root / "nginx"
        if nginx.is_dir() and not nginx.is_symlink():
            for current, directory_names, file_names in nginx.walk(follow_symlinks=False):
                if any((current / name).is_symlink() for name in directory_names):
                    raise StorageError("Configuration templates cannot contain symlinks.")
                relative_directory = current.relative_to(nginx)
                for name in file_names:
                    source = current / name
                    relative = Path("nginx") / relative_directory / name
                    target = destination / relative
                    entry = _copy_regular_file(source, target)
                    entries.append(
                        BackupEntry(
                            relative_path=f"config/{relative.as_posix()}",
                            size_bytes=entry.size_bytes,
                            sha256=entry.sha256,
                        )
                    )
        return entries

    def _write_manifest(self, directory: Path, manifest: BackupManifest) -> None:
        payload = (
            json.dumps(
                manifest.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
        manifest_path = directory / _MANIFEST_NAME
        checksum_path = directory / _MANIFEST_CHECKSUM_NAME
        manifest_path.write_bytes(payload)
        manifest_path.chmod(0o600)
        digest, _ = sha256_file(manifest_path)
        checksum_path.write_text(f"{digest}  {_MANIFEST_NAME}\n", encoding="ascii")
        checksum_path.chmod(0o600)
        self._fsync_directory(directory)

    def _verify_directory(
        self,
        directory: Path,
        *,
        expected_backup_id: str,
    ) -> BackupVerificationReport:
        _safe_backup_id(expected_backup_id)
        if directory.is_symlink() or not directory.is_dir():
            raise StorageError("The backup directory is unavailable.")
        manifest_path = directory / _MANIFEST_NAME
        checksum_path = directory / _MANIFEST_CHECKSUM_NAME
        metadata = _regular_file(manifest_path, message="The backup manifest is unavailable.")
        if metadata.st_size > _MAX_MANIFEST_BYTES:
            raise ValidationError("The backup manifest is too large.")
        _regular_file(checksum_path, message="The manifest checksum is unavailable.")
        checksum_parts = checksum_path.read_text(encoding="ascii").split()
        if len(checksum_parts) != 2 or checksum_parts[1] != _MANIFEST_NAME:
            raise ValidationError("The manifest checksum file is invalid.")
        expected_digest = checksum_parts[0]
        actual_digest, _ = sha256_file(manifest_path)
        if expected_digest != actual_digest:
            raise ValidationError("The backup manifest checksum is invalid.")
        manifest = self._parse_manifest(manifest_path.read_bytes())
        if manifest.backup_id != expected_backup_id:
            raise ValidationError("The backup identifier does not match its directory.")
        expected_files = {_MANIFEST_NAME, _MANIFEST_CHECKSUM_NAME}
        for entry in manifest.entries:
            relative = _safe_relative_path(entry.relative_path)
            path = directory.joinpath(*relative.parts)
            file_metadata = _regular_file(path, message="A backup file is unavailable.")
            if file_metadata.st_size != entry.size_bytes:
                raise ValidationError("A backup file size does not match the manifest.")
            digest, size = sha256_file(path)
            if size != entry.size_bytes or digest != entry.sha256:
                raise ValidationError("A backup file checksum does not match the manifest.")
            expected_files.add(relative.as_posix())
        actual_files: set[str] = set()
        for current, directory_names, file_names in directory.walk(follow_symlinks=False):
            if any((current / name).is_symlink() for name in directory_names):
                raise ValidationError("Backup directories cannot contain symlinks.")
            for name in file_names:
                path = current / name
                _regular_file(path, message="Backup content must be regular files.")
                actual_files.add(path.relative_to(directory).as_posix())
        if actual_files != expected_files:
            raise ValidationError("The backup contains files not declared by its manifest.")
        database_path = directory / "database" / "software-hub.sqlite3"
        _sqlite_integrity_check(database_path)
        database_revision = _sqlite_schema_revision(database_path)
        if database_revision != manifest.database_revision:
            raise ValidationError("The backup database revision does not match the manifest.")
        return BackupVerificationReport(
            backup_id=manifest.backup_id,
            created_at=manifest.created_at,
            file_count=len(manifest.entries),
            total_bytes=manifest.total_bytes,
            database_revision=manifest.database_revision,
            checksum_verified=True,
            database_integrity_verified=True,
        )

    def _parse_manifest(self, payload: bytes) -> BackupManifest:
        try:
            raw = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("The backup manifest is invalid JSON.") from exc
        if not isinstance(raw, Mapping) or raw.get("manifest_version") != _MANIFEST_VERSION:
            raise ValidationError("The backup manifest version is unsupported.")
        backup_id = _safe_backup_id(str(raw.get("backup_id", "")))
        try:
            created_at = datetime.fromisoformat(str(raw["created_at"]))
        except (KeyError, ValueError) as exc:
            raise ValidationError("The backup timestamp is invalid.") from exc
        if created_at.tzinfo is None:
            raise ValidationError("The backup timestamp must contain a timezone.")
        database_revision = str(raw.get("database_revision", ""))
        if not _REVISION_PATTERN.fullmatch(database_revision):
            raise ValidationError("The backup database revision is invalid.")
        raw_entries = raw.get("entries")
        if not isinstance(raw_entries, list):
            raise ValidationError("The backup manifest entries are invalid.")
        entries: list[BackupEntry] = []
        seen_paths: set[str] = set()
        for item in raw_entries:
            if not isinstance(item, Mapping):
                raise ValidationError("The backup manifest entries are invalid.")
            relative = _safe_relative_path(str(item.get("relative_path", ""))).as_posix()
            if relative in seen_paths:
                raise ValidationError("The backup manifest contains duplicate paths.")
            seen_paths.add(relative)
            try:
                size = int(item["size_bytes"])
                digest = str(item["sha256"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("The backup manifest entries are invalid.") from exc
            valid_digest = len(digest) == 64 and all(char in "0123456789abcdef" for char in digest)
            if size < 0 or not valid_digest:
                raise ValidationError("The backup manifest entries are invalid.")
            entries.append(BackupEntry(relative, size, digest))
        if "database/software-hub.sqlite3" not in seen_paths:
            raise ValidationError("The backup database entry is missing.")
        return BackupManifest(
            backup_id=backup_id,
            created_at=created_at.astimezone(UTC),
            app_version=str(raw.get("app_version", "unknown"))[:64],
            database_revision=database_revision,
            entries=tuple(entries),
        )

    def _restore_verified_backup(self, backup_id: str) -> None:
        backup = self._backup_directory(backup_id)
        token = uuid4().hex
        storage_parent = self.storage_root.parent
        database_parent = self.database_path.parent
        storage_stage = storage_parent / f".{self.storage_root.name}.restore-{token}"
        storage_rollback = storage_parent / f".{self.storage_root.name}.rollback-{token}"
        database_stage = database_parent / f".{self.database_path.name}.restore-{token}"
        database_rollback = database_parent / f".{self.database_path.name}.rollback-{token}"
        storage_replaced = database_replaced = False
        try:
            shutil.copytree(backup / "storage", storage_stage, symlinks=False)
            temporary_relative = self.settings.temporary_root.relative_to(self.storage_root)
            (storage_stage / temporary_relative).mkdir(mode=0o750, parents=True, exist_ok=True)
            _copy_regular_file(backup / "database" / "software-hub.sqlite3", database_stage)
            _sqlite_integrity_check(database_stage)
            if self.storage_root.exists():
                self.storage_root.replace(storage_rollback)
            storage_stage.replace(self.storage_root)
            storage_replaced = True
            self._move_database_aside(database_rollback)
            database_stage.replace(self.database_path)
            database_replaced = True
            upgrade_database(self.settings.database_url)
            _sqlite_integrity_check(self.database_path)
            shutil.rmtree(storage_rollback, ignore_errors=True)
            shutil.rmtree(database_rollback, ignore_errors=True)
        except Exception:
            if database_replaced:
                self.database_path.unlink(missing_ok=True)
            if database_rollback.exists():
                self._restore_database_rollback(database_rollback)
            if storage_replaced:
                shutil.rmtree(self.storage_root, ignore_errors=True)
            if storage_rollback.exists():
                storage_rollback.replace(self.storage_root)
            raise
        finally:
            shutil.rmtree(storage_stage, ignore_errors=True)
            database_stage.unlink(missing_ok=True)
            shutil.rmtree(database_rollback, ignore_errors=True)

    def _move_database_aside(self, rollback: Path) -> None:
        rollback.mkdir(mode=0o700, parents=True)
        for suffix in ("", "-wal", "-shm"):
            source = Path(f"{self.database_path}{suffix}")
            if source.exists() or source.is_symlink():
                source.replace(rollback / source.name)

    def _restore_database_rollback(self, rollback: Path) -> None:
        for source in rollback.iterdir():
            source.replace(self.database_path.parent / source.name)

    def _estimate_source_bytes(self) -> int:
        total = self.database_path.stat().st_size if self.database_path.exists() else 0
        if self.storage_root.is_dir() and not self.storage_root.is_symlink():
            temporary_relative = self.settings.temporary_root.relative_to(self.storage_root)
            for current, directory_names, file_names in self.storage_root.walk(
                follow_symlinks=False
            ):
                relative_directory = current.relative_to(self.storage_root)
                if any((current / name).is_symlink() for name in directory_names):
                    raise StorageError("Private storage cannot contain symbolic links.")
                directory_names[:] = [
                    name
                    for name in directory_names
                    if not self._excluded_storage_path(
                        relative_directory / name,
                        temporary_relative,
                    )
                ]
                for name in file_names:
                    path = current / name
                    metadata = _regular_file(
                        path,
                        message="A storage file is unavailable for backup.",
                    )
                    total += metadata.st_size
        return total

    def _backup_directory(self, backup_id: str) -> Path:
        selected = _safe_backup_id(backup_id)
        root = self.backup_root.resolve(strict=True)
        candidate = root / selected
        if candidate.is_symlink() or not candidate.is_dir():
            raise StorageError("The requested backup does not exist.")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise StorageError("The requested backup path is unsafe.")
        return resolved

    def _recognized_backup_directories(self) -> tuple[Path, ...]:
        ensure_private_directory(self.backup_root)
        entries = [
            entry
            for entry in self.backup_root.iterdir()
            if (
                _BACKUP_ID_PATTERN.fullmatch(entry.name)
                and entry.is_dir()
                and not entry.is_symlink()
            )
        ]
        return tuple(entries)

    def _new_backup_id(self) -> str:
        timestamp = utc_now().strftime("%Y%m%dT%H%M%S%fZ")
        return f"{_BACKUP_PREFIX}{timestamp}-{uuid4().hex[:8]}"

    @contextmanager
    def _operation_lock(self) -> Iterator[None]:
        ensure_private_directory(self.backup_root)
        lock_path = self.backup_root / _LOCK_NAME
        descriptor: int | None = None
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(descriptor)
            yield
        except FileExistsError as exc:
            raise StorageError("Another backup or restore operation is already running.") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
                lock_path.unlink(missing_ok=True)

    def _audit(
        self,
        *,
        action: AuditAction,
        result: AuditResult,
        backup_id: str,
        metadata: Mapping[str, Any],
    ) -> None:
        try:
            database = create_database(self.settings)
            try:
                with database.transaction() as session:
                    append_audit_event(
                        session,
                        action=action,
                        result=result,
                        entity_type="backup",
                        entity_id=backup_id,
                        request_id="cli",
                        metadata=metadata,
                    )
            finally:
                database.dispose()
        except Exception as exc:  # noqa: BLE001 - audit failure cannot hide primary result.
            logger.warning(
                "backup_audit_failed",
                extra={"exception_type": type(exc).__name__},
            )

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor: int | None = None
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            os.fsync(descriptor)
        finally:
            if descriptor is not None:
                os.close(descriptor)


@contextmanager
def _null_context() -> Iterator[None]:
    yield
