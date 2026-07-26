"""Chunked application-owned temporary upload tests."""

import os
from io import BytesIO
from pathlib import Path

import pytest
from app.core.config import AppSettings
from app.core.exceptions import FileValidationError, PayloadTooLarge
from app.storage.filename import normalize_original_filename
from app.storage.manager import StorageManager
from app.storage.upload import StreamedUpload, _copy_stream, stream_upload_to_temporary
from app.storage.validation import normalize_display_filename
from starlette.datastructures import Headers, UploadFile
from tests.async_utils import run_coroutine


def _upload(filename: str, body: bytes, content_type: str = "text/plain") -> UploadFile:
    return UploadFile(
        BytesIO(body),
        size=len(body),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_stream_upload_calculates_hash_sample_and_private_file(
    test_settings: AppSettings,
) -> None:
    manager = StorageManager.from_settings(test_settings)
    manager.initialize()
    body = b"PK\x03\x04" + b"a" * 128
    upload = _upload("tool.zip", body)

    async def run_upload() -> StreamedUpload:
        return await stream_upload_to_temporary(
            upload,
            settings=test_settings,
            paths=manager.paths,
        )

    result = run_coroutine(run_upload())
    assert result.size_bytes == len(body)
    assert result.signature_sample == body
    assert result.path_plan.temporary_path.read_bytes() == body
    assert result.client_content_type == "text/plain"
    if os.name != "nt":
        assert result.path_plan.temporary_path.stat().st_mode & 0o777 == 0o640


def test_copy_stream_rejects_oversized_and_empty(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.upload"
    with pytest.raises(PayloadTooLarge):
        _copy_stream(BytesIO(b"12345"), oversized, 4, 2, 4)

    empty = tmp_path / "empty.upload"
    with pytest.raises(FileValidationError, match="Empty"):
        _copy_stream(BytesIO(b""), empty, 10, 2, 4)


def test_display_filename_keeps_extension(test_settings: AppSettings) -> None:
    original = stream_original = normalize_original_filename(
        "tool.zip",
        allowed_extensions=test_settings.allowed_extensions,
    )
    assert (
        normalize_display_filename(
            "Pretty Tool.zip",
            original=stream_original,
            allowed_extensions=test_settings.allowed_extensions,
        )
        == "Pretty Tool.zip"
    )
    assert (
        normalize_display_filename(
            "",
            original=original,
            allowed_extensions=test_settings.allowed_extensions,
        )
        == "tool.zip"
    )
    with pytest.raises(FileValidationError, match="keep"):
        normalize_display_filename(
            "Pretty Tool.exe",
            original=original,
            allowed_extensions=test_settings.allowed_extensions,
        )


def test_declared_upload_size_over_limit_is_rejected(test_settings: AppSettings) -> None:
    manager = StorageManager.from_settings(test_settings)
    manager.initialize()
    upload = UploadFile(
        BytesIO(b"PK\x03\x04"),
        size=test_settings.max_upload_size + 1,
        filename="too-large.zip",
    )

    async def run_upload() -> StreamedUpload:
        return await stream_upload_to_temporary(
            upload,
            settings=test_settings,
            paths=manager.paths,
        )

    with pytest.raises(PayloadTooLarge):
        run_coroutine(run_upload())
