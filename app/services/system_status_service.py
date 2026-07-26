"""Bounded operational checks for health endpoints and the admin dashboard."""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from app.core.time import utc_now
from app.database.session import Database
from app.storage.disk import DiskSpace, get_disk_space
from app.storage.manager import StorageManager

logger = logging.getLogger(__name__)

_BACKUP_DIRECTORY_PREFIX = "software-hub-backup-"
_BACKUP_MANIFEST_NAME = "manifest.json"
_BACKUP_MANIFEST_SUFFIX = ".manifest.json"


class ComponentState(StrEnum):
    """Safe component states shared by health and administration views."""

    OK = "ok"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    """One component result without internal paths or exception messages."""

    state: ComponentState
    label: str

    @property
    def is_ok(self) -> bool:
        return self.state is ComponentState.OK


@dataclass(frozen=True, slots=True)
class DiskStatus:
    """Capacity snapshot safe for the authenticated operations dashboard."""

    state: ComponentState
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    reserve_bytes: int

    @property
    def is_ok(self) -> bool:
        return self.state is ComponentState.OK

    @property
    def used_percent(self) -> float | None:
        total_bytes = self.total_bytes
        used_bytes = self.used_bytes
        if total_bytes is None or total_bytes == 0 or used_bytes is None:
            return None
        return round((used_bytes / total_bytes) * 100, 1)

    @property
    def free_display(self) -> str:
        return format_bytes(self.free_bytes)

    @property
    def reserve_display(self) -> str:
        return format_bytes(self.reserve_bytes)


@dataclass(frozen=True, slots=True)
class BackupStatus:
    """Latest recognized backup manifest without exposing its filesystem name."""

    last_manifest_at: datetime | None

    @property
    def available(self) -> bool:
        return self.last_manifest_at is not None


@dataclass(frozen=True, slots=True)
class SystemStatusSnapshot:
    """Combined bounded status used by readiness and the admin dashboard."""

    checked_at: datetime
    database: ComponentStatus
    storage: ComponentStatus
    disk: DiskStatus
    backup: BackupStatus

    @property
    def ready(self) -> bool:
        return self.database.is_ok and self.storage.is_ok and self.disk.is_ok


def format_bytes(value: int | None) -> str:
    """Format a byte count for an authenticated human-facing dashboard."""

    if value is None:
        return "—"
    amount = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            precision = 0 if unit == "B" else 1
            return f"{amount:.{precision}f} {unit}"
        amount /= 1024
    return f"{value} B"


class SystemStatusService:
    """Inspect database, private storage, capacity and backup manifests."""

    def __init__(self, database: Database, storage: StorageManager) -> None:
        self.database = database
        self.storage = storage

    def snapshot(self) -> SystemStatusSnapshot:
        """Return one bounded status snapshot without raising infrastructure details."""

        database_status = self._database_status()
        storage_status = self._storage_status()
        disk_status = self._disk_status()
        backup_status = self._backup_status()
        snapshot = SystemStatusSnapshot(
            checked_at=utc_now(),
            database=database_status,
            storage=storage_status,
            disk=disk_status,
            backup=backup_status,
        )
        if not snapshot.ready:
            logger.warning(
                "system_status_unhealthy",
                extra={
                    "database_status": snapshot.database.state.value,
                    "storage_status": snapshot.storage.state.value,
                    "disk_status": snapshot.disk.state.value,
                },
            )
        return snapshot

    def _database_status(self) -> ComponentStatus:
        if self.database.ping():
            return ComponentStatus(ComponentState.OK, "База даних доступна")
        return ComponentStatus(ComponentState.ERROR, "База даних недоступна")

    def _storage_status(self) -> ComponentStatus:
        if not self.storage.initialized:
            return ComponentStatus(ComponentState.ERROR, "Сховище не ініціалізоване")
        try:
            for directory in self.storage.paths.required_directories():
                metadata = directory.lstat()
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    return ComponentStatus(ComponentState.ERROR, "Сховище недоступне")
                if not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
                    return ComponentStatus(ComponentState.ERROR, "Сховище недоступне")
        except OSError:
            return ComponentStatus(ComponentState.ERROR, "Сховище недоступне")
        return ComponentStatus(ComponentState.OK, "Сховище доступне")

    def _disk_status(self) -> DiskStatus:
        try:
            space: DiskSpace = get_disk_space(self.storage.paths.root)
        except Exception as exc:  # noqa: BLE001 - status boundary must remain safe.
            logger.warning(
                "disk_status_check_failed",
                extra={"exception_type": type(exc).__name__},
            )
            return DiskStatus(
                state=ComponentState.ERROR,
                total_bytes=None,
                used_bytes=None,
                free_bytes=None,
                reserve_bytes=self.storage.minimum_free_bytes,
            )
        state = (
            ComponentState.OK
            if space.free >= self.storage.minimum_free_bytes
            else ComponentState.ERROR
        )
        return DiskStatus(
            state=state,
            total_bytes=space.total,
            used_bytes=space.used,
            free_bytes=space.free,
            reserve_bytes=self.storage.minimum_free_bytes,
        )

    def _backup_status(self) -> BackupStatus:
        latest: datetime | None = None
        try:
            entries = tuple(self.storage.paths.backups.iterdir())
        except OSError:
            return BackupStatus(last_manifest_at=None)
        for entry in entries:
            manifest = self._recognized_manifest(entry)
            if manifest is None:
                continue
            try:
                metadata = manifest.lstat()
            except OSError:
                continue
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                continue
            timestamp = datetime.fromtimestamp(metadata.st_mtime, tz=UTC)
            if latest is None or timestamp > latest:
                latest = timestamp
        return BackupStatus(last_manifest_at=latest)

    @staticmethod
    def _recognized_manifest(entry: Path) -> Path | None:
        try:
            if entry.is_symlink():
                return None
            if entry.is_dir() and entry.name.startswith(_BACKUP_DIRECTORY_PREFIX):
                return entry / _BACKUP_MANIFEST_NAME
            if (
                entry.is_file()
                and entry.name.startswith(_BACKUP_DIRECTORY_PREFIX)
                and entry.name.endswith(_BACKUP_MANIFEST_SUFFIX)
            ):
                return entry
        except OSError:
            return None
        return None
