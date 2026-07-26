"""Conservative cleanup of app-generated temporary upload files."""

import stat
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import StorageError
from app.storage.filename import is_temporary_filename


@dataclass(frozen=True, slots=True)
class CleanupReport:
    """Summary of one dry-run or destructive cleanup pass."""

    examined: int
    eligible: int
    deleted: int
    reclaimed_bytes: int
    skipped: int
    errors: int


def cleanup_temporary_files(
    temporary_root: Path,
    *,
    max_age_seconds: int,
    dry_run: bool = True,
    now_timestamp: float | None = None,
) -> CleanupReport:
    """Remove only stale regular files matching the generated ``*.upload`` pattern."""

    if max_age_seconds <= 0:
        raise ValueError("Temporary file age must be positive.")
    if temporary_root.is_symlink():
        raise StorageError("Temporary storage is not a safe directory.")
    try:
        root = temporary_root.resolve(strict=True)
    except OSError as exc:
        raise StorageError("Temporary storage is unavailable.") from exc
    if not root.is_dir():
        raise StorageError("Temporary storage is not a safe directory.")

    cutoff = (now_timestamp if now_timestamp is not None else time.time()) - max_age_seconds
    examined = eligible = deleted = reclaimed = skipped = errors = 0

    for current, directory_names, file_names in root.walk(follow_symlinks=False):
        directory_names[:] = [name for name in directory_names if not (current / name).is_symlink()]
        for name in file_names:
            examined += 1
            candidate = current / name
            try:
                metadata = candidate.lstat()
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                    skipped += 1
                    continue
                if not is_temporary_filename(name) or metadata.st_mtime > cutoff:
                    skipped += 1
                    continue
                eligible += 1
                if dry_run:
                    continue
                candidate.unlink()
                deleted += 1
                reclaimed += metadata.st_size
            except FileNotFoundError:
                skipped += 1
            except OSError:
                errors += 1

    return CleanupReport(
        examined=examined,
        eligible=eligible,
        deleted=deleted,
        reclaimed_bytes=reclaimed,
        skipped=skipped,
        errors=errors,
    )
