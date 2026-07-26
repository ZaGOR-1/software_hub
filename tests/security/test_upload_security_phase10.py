"""Security-specific upload validation assertions."""

from io import BytesIO
from pathlib import Path

import pytest
from app.core.config import AppSettings
from app.core.exceptions import FileValidationError, StorageError
from app.storage.filename import normalize_original_filename
from app.storage.signatures import SignatureAssessment, validate_file_signature
from app.storage.upload import _copy_stream
from app.storage.validation import normalize_display_filename


def test_spoofed_browser_mime_cannot_change_magic_detection() -> None:
    result = validate_file_signature(".exe", b"PK\x03\x04archive")
    assert result.assessment is SignatureAssessment.MISMATCH
    assert result.detected is not None
    assert result.detected.extension == ".zip"


def test_interrupted_stream_does_not_report_success(tmp_path: Path) -> None:
    class BrokenStream(BytesIO):
        calls = 0

        def read(self, size: int | None = -1) -> bytes:
            self.calls += 1
            if self.calls > 1:
                raise OSError("connection interrupted")
            return super().read(size)

    destination = tmp_path / "broken.upload"
    with pytest.raises(StorageError, match="temporary upload"):
        _copy_stream(BrokenStream(b"PK\x03\x04payload"), destination, 100, 4, 16)


def test_display_filename_path_is_rejected(test_settings: AppSettings) -> None:
    original = normalize_original_filename(
        "tool.zip",
        allowed_extensions=test_settings.allowed_extensions,
    )
    with pytest.raises(FileValidationError):
        normalize_display_filename(
            "../tool.zip",
            original=original,
            allowed_extensions=test_settings.allowed_extensions,
        )
