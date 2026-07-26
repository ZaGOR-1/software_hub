"""Adversarial tests for storage traversal and filename confusion."""

from pathlib import Path
from urllib.parse import unquote

import pytest
from app.core.exceptions import FileValidationError, StorageError
from app.storage.filename import normalize_original_filename
from app.storage.paths import ensure_private_directory, safe_resolve


@pytest.mark.parametrize(
    "payload",
    [
        "../secret.exe",
        "..%2fsecret.exe",
        "%2e%2e/secret.exe",
        "%252e%252e%252fsecret.exe",
        r"..\secret.exe",
        "/etc/passwd",
    ],
)
def test_encoded_and_cross_platform_traversal_never_resolves_outside(
    tmp_path: Path,
    payload: str,
) -> None:
    root = ensure_private_directory(tmp_path / "root")
    decoded = unquote(unquote(payload))
    with pytest.raises(StorageError):
        safe_resolve(root, decoded)


@pytest.mark.parametrize(
    "payload",
    [
        "invoice.pdf.exe",
        "archive.exe.zip",
        "image.jpg.exe",
        "report.docx.exe",
        "script.js.zip",
        "photo\u202egpj.exe",
        "tool.exe\x00.jpg",
    ],
)
def test_filename_confusion_payloads_are_rejected(payload: str) -> None:
    with pytest.raises(FileValidationError):
        normalize_original_filename(
            payload,
            allowed_extensions=(".exe", ".msi", ".zip", ".7z"),
        )
