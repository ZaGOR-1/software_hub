"""Safe storage layout construction and path containment checks."""

import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from secrets import token_hex
from typing import Final

from app.core.config import AppSettings
from app.core.constants import STORAGE_DIRECTORY_MODE
from app.core.exceptions import StorageError

_PROBE_PREFIX: Final[str] = ".software-hub-write-probe-"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StoragePaths:
    """Resolved directories owned by the application storage layer."""

    root: Path
    software: Path
    icons: Path
    imports: Path
    temporary: Path
    quarantine: Path
    backups: Path

    @classmethod
    def from_settings(cls, settings: AppSettings) -> StoragePaths:
        """Build the complete private storage layout from validated settings."""

        root = settings.storage_root
        return cls(
            root=root,
            software=root / "software",
            icons=settings.icons_root,
            imports=root / "import",
            temporary=settings.temporary_root,
            quarantine=settings.quarantine_root,
            backups=settings.backup_root,
        )

    def required_directories(self) -> tuple[Path, ...]:
        """Return directories that must exist before the app accepts requests."""

        return (
            self.root,
            self.software,
            self.icons,
            self.imports,
            self.temporary,
            self.quarantine,
            self.backups,
        )


def _reject_unsafe_relative_path(relative_path: str | Path | PurePosixPath) -> PurePosixPath:
    raw = str(relative_path)
    if not raw or "\x00" in raw or "\\" in raw:
        raise StorageError("The storage path is invalid.")
    raw_parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise StorageError("The storage path is invalid.")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise StorageError("The storage path is invalid.")
    return candidate


def safe_resolve(
    root: Path,
    relative_path: str | Path | PurePosixPath,
    *,
    require_exists: bool = False,
    reject_symlinks: bool = False,
) -> Path:
    """Resolve one relative path and prove it remains inside ``root``."""

    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise StorageError("The storage root is unavailable.") from exc

    relative = _reject_unsafe_relative_path(relative_path)
    unresolved_candidate = resolved_root / Path(*relative.parts)
    if reject_symlinks:
        current = resolved_root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise StorageError("Symbolic links are not allowed in this storage path.")
    try:
        resolved_candidate = unresolved_candidate.resolve(strict=require_exists)
    except OSError as exc:
        raise StorageError("The storage path is unavailable.") from exc

    if resolved_candidate == resolved_root or not resolved_candidate.is_relative_to(resolved_root):
        raise StorageError("The storage path escapes its configured root.")
    return resolved_candidate


def relative_to_root(path: Path, root: Path) -> PurePosixPath:
    """Return a portable relative path after a containment check."""

    try:
        resolved_root = root.resolve(strict=True)
        resolved_path = path.resolve(strict=False)
    except OSError as exc:
        raise StorageError("The storage path is unavailable.") from exc
    if resolved_path == resolved_root or not resolved_path.is_relative_to(resolved_root):
        raise StorageError("The storage path escapes its configured root.")
    return PurePosixPath(resolved_path.relative_to(resolved_root).as_posix())


def ensure_private_directory(path: Path) -> Path:
    """Create and validate one writable non-symlink private directory."""

    _reject_symlink_components(path)
    if _path_lexists(path):
        try:
            existing_metadata = path.lstat()
        except OSError as exc:
            raise StorageError("A required storage directory is unavailable.") from exc
        if stat.S_ISLNK(existing_metadata.st_mode) or not stat.S_ISDIR(existing_metadata.st_mode):
            raise StorageError("A configured storage location is not a real directory.")
    try:
        path.mkdir(mode=STORAGE_DIRECTORY_MODE, parents=True, exist_ok=True)
        metadata = path.lstat()
    except OSError as exc:
        raise StorageError("A required storage directory could not be created.") from exc

    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise StorageError("A configured storage location is not a real directory.")

    try:
        path.chmod(STORAGE_DIRECTORY_MODE)
    except OSError as exc:
        raise StorageError("Storage directory permissions could not be secured.") from exc

    _probe_writable(path)
    return path.resolve(strict=True)


def ensure_private_parent(root: Path, relative_path: str | Path | PurePosixPath) -> Path:
    """Create the parent of a safe relative path without following escaped symlinks."""

    relative = _reject_unsafe_relative_path(relative_path)
    parent_relative = relative.parent
    if str(parent_relative) == ".":
        return root.resolve(strict=True)

    current = root.resolve(strict=True)
    current_relative = PurePosixPath()
    for part in parent_relative.parts:
        current_relative /= part
        current = safe_resolve(root, current_relative, reject_symlinks=True)
        if current.exists() and current.is_symlink():
            raise StorageError("A storage directory cannot be a symbolic link.")
        try:
            current.mkdir(mode=STORAGE_DIRECTORY_MODE, exist_ok=True)
            current.chmod(STORAGE_DIRECTORY_MODE)
        except OSError as exc:
            raise StorageError("A storage directory could not be created securely.") from exc
        if not current.is_dir() or current.is_symlink():
            raise StorageError("A storage path component is not a safe directory.")
    return current


def _path_lexists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if _path_lexists(current) and current.is_symlink():
            raise StorageError("Storage directories cannot contain symbolic links.")


def _probe_writable(directory: Path) -> None:
    token = f"{_PROBE_PREFIX}{os.getpid()}-{token_hex(8)}"
    probe = directory / token
    descriptor: int | None = None
    try:
        descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(descriptor, b"ok")
        os.fsync(descriptor)
    except OSError as exc:
        raise StorageError("A required storage directory is not writable.") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            logger.warning("storage_write_probe_cleanup_failed")
