"""Disk-capacity checks for uploads and startup readiness."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import StorageError


@dataclass(frozen=True, slots=True)
class DiskSpace:
    """Snapshot of filesystem capacity in bytes."""

    total: int
    used: int
    free: int


def get_disk_space(path: Path) -> DiskSpace:
    """Read disk usage for one existing storage directory."""

    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        raise StorageError("Storage capacity could not be determined.") from exc
    return DiskSpace(total=usage.total, used=usage.used, free=usage.free)


def ensure_free_space(
    path: Path,
    *,
    required_bytes: int,
    reserve_bytes: int,
) -> DiskSpace:
    """Require enough capacity for an operation while retaining a safety reserve."""

    if required_bytes < 0 or reserve_bytes < 0:
        raise ValueError("Disk-space requirements cannot be negative.")
    space = get_disk_space(path)
    if required_bytes > space.free or space.free - required_bytes < reserve_bytes:
        raise StorageError(
            "Insufficient free space is available for this file operation.",
            safe_metadata={
                "required_bytes": required_bytes,
                "reserve_bytes": reserve_bytes,
                "free_bytes": space.free,
            },
        )
    return space
