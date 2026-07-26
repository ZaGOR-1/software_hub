"""Private storage inspection and deletion staging for release-file lifecycle actions."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.core.exceptions import StorageError
from app.storage.move import atomic_move
from app.storage.paths import StoragePaths, safe_resolve


class StorageArea(StrEnum):
    """Physical areas that may contain a persisted release file."""

    QUARANTINE = "quarantine"
    SOFTWARE = "software"


@dataclass(frozen=True, slots=True)
class StoredFile:
    """One verified regular file inside a configured private storage root."""

    area: StorageArea
    root: Path
    relative_path: PurePosixPath
    path: Path
    size_bytes: int


@dataclass(frozen=True, slots=True)
class StagedDeletion:
    """A file atomically hidden in temporary storage before metadata deletion."""

    original: StoredFile
    staged_relative_path: PurePosixPath
    staged_path: Path


def inspect_stored_files(
    paths: StoragePaths,
    relative_path: str | Path | PurePosixPath,
) -> tuple[StoredFile, ...]:
    """Return all matching regular files without accepting ambiguous duplicates."""

    relative = PurePosixPath(str(relative_path))
    matches: list[StoredFile] = []
    for area, root in (
        (StorageArea.QUARANTINE, paths.quarantine),
        (StorageArea.SOFTWARE, paths.software),
    ):
        candidate = safe_resolve(root, relative, reject_symlinks=True)
        if not candidate.exists():
            continue
        try:
            metadata = candidate.lstat()
        except OSError as exc:
            raise StorageError("The stored file is unavailable.") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise StorageError("Stored release content must be a regular file.")
        matches.append(
            StoredFile(
                area=area,
                root=root,
                relative_path=relative,
                path=candidate,
                size_bytes=metadata.st_size,
            )
        )
    return tuple(matches)


def locate_stored_file(
    paths: StoragePaths,
    relative_path: str | Path | PurePosixPath,
) -> StoredFile:
    """Require exactly one physical file for the supplied metadata path."""

    matches = inspect_stored_files(paths, relative_path)
    if not matches:
        raise StorageError("The physical file is missing from private storage.")
    if len(matches) > 1:
        raise StorageError("The physical file exists in multiple storage locations.")
    return matches[0]


def stage_for_permanent_deletion(
    paths: StoragePaths,
    stored_file: StoredFile,
) -> StagedDeletion:
    """Atomically hide a file before the database row is removed."""

    staged_relative = PurePosixPath("deletions") / f"{uuid4().hex}.delete"
    result = atomic_move(
        source_root=stored_file.root,
        source_relative_path=stored_file.relative_path,
        destination_root=paths.temporary,
        destination_relative_path=staged_relative,
    )
    return StagedDeletion(
        original=stored_file,
        staged_relative_path=staged_relative,
        staged_path=result.destination,
    )


def restore_staged_deletion(paths: StoragePaths, staged: StagedDeletion) -> StoredFile:
    """Compensate a failed metadata transaction by restoring the original file."""

    atomic_move(
        source_root=paths.temporary,
        source_relative_path=staged.staged_relative_path,
        destination_root=staged.original.root,
        destination_relative_path=staged.original.relative_path,
    )
    return locate_stored_file(paths, staged.original.relative_path)


def unlink_staged_deletion(paths: StoragePaths, staged: StagedDeletion) -> None:
    """Permanently remove a staged regular file and synchronize its directory."""

    path = safe_resolve(
        paths.temporary,
        staged.staged_relative_path,
        require_exists=True,
        reject_symlinks=True,
    )
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise StorageError("The staged file is unavailable.") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise StorageError("Only a staged regular file can be permanently deleted.")
    try:
        path.unlink()
        _fsync_directory(path.parent)
    except OSError as exc:
        raise StorageError("The staged file could not be permanently deleted.") from exc


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
