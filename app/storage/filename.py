"""Filename normalization and server-generated storage identifiers."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath
from typing import Final
from uuid import uuid4

from app.core.constants import (
    MAXIMUM_FILENAME_BYTES,
    MAXIMUM_FILENAME_LENGTH,
    UPLOAD_TEMPORARY_SUFFIX,
)
from app.core.exceptions import FileValidationError

_STORAGE_FILENAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<identifier>[0-9a-f]{32})(?P<extension>\.[a-z0-9]{1,15})$"
)
_TEMPORARY_FILENAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^[0-9a-f]{{32}}{re.escape(UPLOAD_TEMPORARY_SUFFIX)}$"
)
_WINDOWS_RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
)
_DECEPTIVE_INNER_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".bat",
        ".cmd",
        ".com",
        ".doc",
        ".docm",
        ".docx",
        ".exe",
        ".gif",
        ".hta",
        ".htm",
        ".html",
        ".iso",
        ".jar",
        ".jpeg",
        ".jpg",
        ".js",
        ".lnk",
        ".msi",
        ".pdf",
        ".png",
        ".ps1",
        ".py",
        ".scr",
        ".svg",
        ".txt",
        ".vbs",
        ".xls",
        ".xlsm",
        ".xlsx",
        ".zip",
    }
)
_BIDI_AND_FORMAT_CONTROLS: Final[frozenset[str]] = frozenset(
    {
        "\u061c",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2060",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
        "\ufeff",
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedFilename:
    """Safe metadata extracted from an administrator-supplied filename."""

    value: str
    stem: str
    extension: str


def normalize_original_filename(
    filename: str,
    *,
    allowed_extensions: tuple[str, ...],
) -> NormalizedFilename:
    """Normalize upload metadata and reject deceptive or ambiguous names."""

    if "\x00" in filename:
        raise FileValidationError("The filename is invalid.")
    if filename.endswith((".", " ")):
        raise FileValidationError("Trailing dots and spaces are not allowed.")

    normalized = unicodedata.normalize("NFKC", filename).strip()
    if not normalized or normalized in {".", ".."}:
        raise FileValidationError("The filename is empty or invalid.")
    if normalized.startswith(".") or normalized.endswith((".", " ")):
        raise FileValidationError("Hidden filenames and trailing dots are not allowed.")
    if "/" in normalized or "\\" in normalized:
        raise FileValidationError("The filename cannot contain path separators.")
    if any(character in _BIDI_AND_FORMAT_CONTROLS for character in normalized):
        raise FileValidationError("The filename contains forbidden Unicode controls.")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise FileValidationError("The filename contains control characters.")
    if len(normalized) > MAXIMUM_FILENAME_LENGTH:
        raise FileValidationError("The filename is too long.")
    if len(normalized.encode("utf-8")) > MAXIMUM_FILENAME_BYTES:
        raise FileValidationError("The UTF-8 filename is too long.")

    pure_name = PurePath(normalized)
    extension = pure_name.suffix.casefold()
    normalized_allowlist = tuple(item.casefold() for item in allowed_extensions)
    if extension not in normalized_allowlist:
        raise FileValidationError("The filename extension is not allowed.")

    stem = normalized[: -len(extension)]
    if not stem or stem.casefold() in _WINDOWS_RESERVED_NAMES:
        raise FileValidationError("The filename uses a reserved system name.")

    inner_suffixes = tuple(suffix.casefold() for suffix in pure_name.suffixes[:-1])
    if any(suffix in _DECEPTIVE_INNER_EXTENSIONS for suffix in inner_suffixes):
        raise FileValidationError("Deceptive double extensions are not allowed.")

    return NormalizedFilename(value=normalized, stem=stem, extension=extension)


def generate_storage_filename(extension: str, *, allowed_extensions: tuple[str, ...]) -> str:
    """Generate a non-guessable internal filename independent of user input."""

    normalized = extension.strip().casefold()
    if normalized not in tuple(item.casefold() for item in allowed_extensions):
        raise FileValidationError("The storage filename extension is not allowed.")
    return f"{uuid4().hex}{normalized}"


def generate_temporary_filename() -> str:
    """Generate the only filename pattern eligible for temporary cleanup."""

    return f"{uuid4().hex}{UPLOAD_TEMPORARY_SUFFIX}"


def validate_storage_filename(
    filename: str,
    *,
    allowed_extensions: tuple[str, ...],
) -> str:
    """Validate an internal UUID-based storage filename."""

    match = _STORAGE_FILENAME_PATTERN.fullmatch(filename)
    if match is None:
        raise FileValidationError("The internal storage filename is invalid.")
    extension = match.group("extension")
    if extension not in tuple(item.casefold() for item in allowed_extensions):
        raise FileValidationError("The internal storage extension is not allowed.")
    return filename


def is_temporary_filename(filename: str) -> bool:
    """Return whether cleanup may treat a filename as app-generated temporary data."""

    return _TEMPORARY_FILENAME_PATTERN.fullmatch(filename) is not None


def sharded_relative_path(storage_filename: str) -> PurePosixPath:
    """Place UUID-backed files in stable two-level shards."""

    match = _STORAGE_FILENAME_PATTERN.fullmatch(storage_filename)
    if match is None:
        raise FileValidationError("The internal storage filename is invalid.")
    identifier = match.group("identifier")
    return PurePosixPath(identifier[:2], identifier[2:4], storage_filename)
