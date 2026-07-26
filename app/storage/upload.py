"""Bounded streaming from framework uploads into private temporary storage."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from starlette.datastructures import UploadFile

from app.core.config import AppSettings
from app.core.constants import STORAGE_FILE_MODE
from app.core.exceptions import FileValidationError, PayloadTooLarge, StorageError
from app.storage.disk import ensure_free_space
from app.storage.filename import (
    NormalizedFilename,
    generate_storage_filename,
    generate_temporary_filename,
    sharded_relative_path,
)
from app.storage.hashing import StreamingSHA256
from app.storage.paths import StoragePaths, safe_resolve
from app.storage.validation import normalize_original_filename

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadPathPlan:
    """Server-generated paths independent of the administrator-supplied name."""

    original: NormalizedFilename
    storage_filename: str
    temporary_relative_path: PurePosixPath
    quarantine_relative_path: PurePosixPath
    permanent_relative_path: PurePosixPath
    temporary_path: Path
    quarantine_path: Path
    permanent_path: Path


@dataclass(frozen=True, slots=True)
class StreamedUpload:
    """Metadata calculated while copying one upload with bounded memory."""

    path_plan: UploadPathPlan
    size_bytes: int
    sha256: str
    signature_sample: bytes
    client_content_type: str | None


def plan_upload_paths(
    filename: str,
    *,
    settings: AppSettings,
    paths: StoragePaths,
) -> UploadPathPlan:
    """Normalize metadata and allocate private UUID-based paths."""

    original = normalize_original_filename(
        filename,
        allowed_extensions=settings.allowed_extensions,
    )
    storage_filename = generate_storage_filename(
        original.extension,
        allowed_extensions=settings.allowed_extensions,
    )
    temporary_relative = PurePosixPath(generate_temporary_filename())
    stored_relative = sharded_relative_path(storage_filename)
    return UploadPathPlan(
        original=original,
        storage_filename=storage_filename,
        temporary_relative_path=temporary_relative,
        quarantine_relative_path=stored_relative,
        permanent_relative_path=stored_relative,
        temporary_path=safe_resolve(paths.temporary, temporary_relative),
        quarantine_path=safe_resolve(paths.quarantine, stored_relative),
        permanent_path=safe_resolve(paths.software, stored_relative),
    )


async def stream_upload_to_temporary(
    upload: UploadFile,
    *,
    settings: AppSettings,
    paths: StoragePaths,
) -> StreamedUpload:
    """Copy one framework-spooled upload into app-owned temporary storage."""

    filename = upload.filename or ""
    plan = plan_upload_paths(filename, settings=settings, paths=paths)
    declared_size = upload.size
    if declared_size is not None and declared_size > settings.max_upload_size:
        raise PayloadTooLarge()
    ensure_free_space(
        paths.root,
        required_bytes=declared_size or settings.max_upload_size,
        reserve_bytes=settings.storage_min_free_bytes,
    )

    try:
        await upload.seek(0)
        result = await asyncio.to_thread(
            _copy_stream,
            upload.file,
            plan.temporary_path,
            settings.max_upload_size,
            settings.upload_chunk_size,
            settings.upload_magic_sample_size,
        )
    except FileValidationError, PayloadTooLarge, StorageError:
        _safe_unlink(plan.temporary_path)
        raise
    except Exception as exc:
        _safe_unlink(plan.temporary_path)
        raise StorageError("The uploaded file could not be written safely.") from exc

    return StreamedUpload(
        path_plan=plan,
        size_bytes=result.size_bytes,
        sha256=result.sha256,
        signature_sample=result.signature_sample,
        client_content_type=upload.content_type,
    )


@dataclass(frozen=True, slots=True)
class _CopyResult:
    size_bytes: int
    sha256: str
    signature_sample: bytes


def _copy_stream(
    source: BinaryIO,
    destination: Path,
    max_size: int,
    chunk_size: int,
    sample_size: int,
) -> _CopyResult:
    """Synchronously copy one stream; executed in an asyncio worker thread."""

    descriptor: int | None = None
    digest = StreamingSHA256()
    sample = bytearray()
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        while chunk := source.read(chunk_size):
            if digest.bytes_processed + len(chunk) > max_size:
                raise PayloadTooLarge()
            digest.update(chunk)
            if len(sample) < sample_size:
                sample.extend(chunk[: sample_size - len(sample)])
            _write_all(descriptor, chunk)
        if digest.bytes_processed == 0:
            raise FileValidationError("Empty files cannot be uploaded.")
        os.fsync(descriptor)
        os.fchmod(descriptor, STORAGE_FILE_MODE)
    except FileValidationError, PayloadTooLarge:
        raise
    except OSError as exc:
        raise StorageError("The temporary upload could not be stored.") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)

    return _CopyResult(
        size_bytes=digest.bytes_processed,
        sha256=digest.hexdigest(),
        signature_sample=bytes(sample),
    )


def _write_all(descriptor: int, chunk: bytes) -> None:
    view = memoryview(chunk)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("Short write while storing an upload.")
        view = view[written:]


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("temporary_upload_cleanup_failed")
