"""Atomic same-filesystem moves with private file permissions."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.constants import STORAGE_FILE_MODE
from app.core.exceptions import StorageError
from app.storage.paths import ensure_private_parent, safe_resolve


@dataclass(frozen=True, slots=True)
class MoveResult:
    """Result metadata for a completed atomic move."""

    destination: Path
    size_bytes: int


def harden_file_permissions(path: Path) -> None:
    """Remove executable, set-id and world-access bits from a regular file."""

    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise StorageError("Only regular files can be stored.")
        path.chmod(STORAGE_FILE_MODE)
    except StorageError:
        raise
    except OSError as exc:
        raise StorageError("Stored file permissions could not be secured.") from exc


def atomic_move(
    *,
    source_root: Path,
    source_relative_path: str | Path | PurePosixPath,
    destination_root: Path,
    destination_relative_path: str | Path | PurePosixPath,
) -> MoveResult:
    """Atomically move one regular file without crossing filesystems or overwriting."""

    source = safe_resolve(
        source_root,
        source_relative_path,
        require_exists=True,
        reject_symlinks=True,
    )
    destination = safe_resolve(
        destination_root,
        destination_relative_path,
        require_exists=False,
    )
    destination_parent = ensure_private_parent(destination_root, destination_relative_path)

    try:
        source_metadata = source.lstat()
    except OSError as exc:
        raise StorageError("The source file is unavailable.") from exc
    if stat.S_ISLNK(source_metadata.st_mode) or not stat.S_ISREG(source_metadata.st_mode):
        raise StorageError("Only regular files can be moved into storage.")
    if destination.exists() or destination.is_symlink():
        raise StorageError("The destination storage filename already exists.")

    try:
        destination_device = destination_parent.stat().st_dev
    except OSError as exc:
        raise StorageError("The destination storage directory is unavailable.") from exc
    if source_metadata.st_dev != destination_device:
        raise StorageError("Atomic storage moves require the same filesystem.")

    harden_file_permissions(source)
    _fsync_file(source)
    try:
        source.replace(destination)
        _fsync_directory(destination_parent)
    except OSError as exc:
        raise StorageError("The file could not be moved atomically.") from exc

    return MoveResult(destination=destination, size_bytes=source_metadata.st_size)


def _fsync_file(path: Path) -> None:
    descriptor: int | None = None
    try:
        flags = os.O_RDWR if os.name == "nt" else os.O_RDONLY
        descriptor = os.open(path, flags | getattr(os, "O_BINARY", 0))
        os.fsync(descriptor)
    except OSError as exc:
        raise StorageError("The file could not be synchronized before moving.") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        os.fsync(descriptor)
    except OSError as exc:
        raise StorageError("The storage directory could not be synchronized.") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
