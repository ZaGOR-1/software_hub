"""Tests for safe upload filename metadata and internal identifiers."""

from pathlib import PurePosixPath

import pytest
from app.core.exceptions import FileValidationError
from app.storage.filename import (
    generate_storage_filename,
    generate_temporary_filename,
    is_temporary_filename,
    normalize_original_filename,
    sharded_relative_path,
    validate_storage_filename,
)

ALLOWED = (".exe", ".msi", ".zip", ".7z")


def test_normalize_original_filename_preserves_safe_unicode_metadata() -> None:
    normalized = normalize_original_filename(
        "  Корисна утиліта 2.0.EXE",
        allowed_extensions=ALLOWED,
    )

    assert normalized.value == "Корисна утиліта 2.0.EXE"
    assert normalized.stem == "Корисна утиліта 2.0"
    assert normalized.extension == ".exe"


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
        ".",
        "..",
        ".hidden.exe",
        "tool.exe.",
        "tool.exe ",
        "../tool.exe",
        r"folder\tool.exe",
        "tool\x00.exe",
        "tool\n.exe",
        "safe\u202etxt.exe",
        "CON.exe",
        "nul.zip",
        "document.pdf.exe",
        "photo.jpg.exe",
        "script.ps1.zip",
        "installer.exe.zip",
        "tool.bin",
    ],
)
def test_rejects_unsafe_or_deceptive_original_filenames(filename: str) -> None:
    with pytest.raises(FileValidationError):
        normalize_original_filename(filename, allowed_extensions=ALLOWED)


def test_nfkc_normalization_cannot_hide_a_path_separator() -> None:
    with pytest.raises(FileValidationError, match="path separators"):
        normalize_original_filename("folder／tool.exe", allowed_extensions=ALLOWED)


def test_numeric_version_suffixes_are_not_treated_as_double_extensions() -> None:
    normalized = normalize_original_filename("7zip.24.09.exe", allowed_extensions=ALLOWED)
    assert normalized.extension == ".exe"


def test_filename_length_is_bounded_by_utf8_bytes() -> None:
    with pytest.raises(FileValidationError, match="UTF-8"):
        normalize_original_filename(f"{'я' * 126}.exe", allowed_extensions=ALLOWED)


def test_internal_names_are_uuid_based_and_sharded() -> None:
    generated = generate_storage_filename(".EXE", allowed_extensions=ALLOWED)
    validated = validate_storage_filename(generated, allowed_extensions=ALLOWED)
    relative = sharded_relative_path(validated)

    assert validated == generated
    assert len(generated) == 36
    assert relative == PurePosixPath(generated[:2], generated[2:4], generated)


def test_invalid_internal_names_and_extensions_are_rejected() -> None:
    with pytest.raises(FileValidationError):
        generate_storage_filename(".pdf", allowed_extensions=ALLOWED)
    with pytest.raises(FileValidationError):
        validate_storage_filename("../../tool.exe", allowed_extensions=ALLOWED)
    with pytest.raises(FileValidationError):
        validate_storage_filename(f"{'a' * 32}.pdf", allowed_extensions=ALLOWED)
    with pytest.raises(FileValidationError):
        sharded_relative_path("not-a-storage-name.exe")


def test_temporary_names_have_a_cleanup_allowlisted_pattern() -> None:
    filename = generate_temporary_filename()
    assert is_temporary_filename(filename)
    assert not is_temporary_filename("manual.upload")
    assert not is_temporary_filename(f"{'A' * 32}.upload")
