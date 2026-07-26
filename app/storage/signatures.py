"""Magic-byte detection for the MVP upload allowlist."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class SignatureAssessment(StrEnum):
    """Confidence result comparing an extension with detected bytes."""

    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DetectedFileType:
    """One recognized binary container type."""

    extension: str
    mime_type: str
    label: str


@dataclass(frozen=True, slots=True)
class SignatureValidation:
    """Result of comparing a normalized filename extension with magic bytes."""

    assessment: SignatureAssessment
    expected_extension: str
    detected: DetectedFileType | None
    reason: str


_PE: Final[DetectedFileType] = DetectedFileType(
    extension=".exe",
    mime_type="application/vnd.microsoft.portable-executable",
    label="Windows PE executable",
)
_MSI: Final[DetectedFileType] = DetectedFileType(
    extension=".msi",
    mime_type="application/x-msi",
    label="Microsoft Compound File Binary",
)
_ZIP: Final[DetectedFileType] = DetectedFileType(
    extension=".zip",
    mime_type="application/zip",
    label="ZIP archive",
)
_SEVEN_ZIP: Final[DetectedFileType] = DetectedFileType(
    extension=".7z",
    mime_type="application/x-7z-compressed",
    label="7-Zip archive",
)

_COMPOUND_FILE_SIGNATURE: Final[bytes] = bytes.fromhex("D0CF11E0A1B11AE1")
_SEVEN_ZIP_SIGNATURE: Final[bytes] = bytes.fromhex("377ABCAF271C")
_ZIP_SIGNATURES: Final[tuple[bytes, ...]] = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)


def _looks_like_pe(sample: bytes) -> bool:
    if len(sample) < 64 or sample[:2] != b"MZ":
        return False
    pe_offset = int.from_bytes(sample[0x3C:0x40], "little")
    if pe_offset < 64 or pe_offset + 4 > len(sample):
        return False
    return sample[pe_offset : pe_offset + 4] == b"PE\x00\x00"


def detect_file_type(sample: bytes) -> DetectedFileType | None:
    """Detect one supported file type using server-read bytes only."""

    if _looks_like_pe(sample):
        return _PE
    if sample.startswith(_COMPOUND_FILE_SIGNATURE):
        return _MSI
    if sample.startswith(_SEVEN_ZIP_SIGNATURE):
        return _SEVEN_ZIP
    if any(sample.startswith(signature) for signature in _ZIP_SIGNATURES):
        return _ZIP
    return None


def validate_file_signature(extension: str, sample: bytes) -> SignatureValidation:
    """Compare a normalized allowed extension with detected magic bytes."""

    expected = extension.strip().casefold()
    detected = detect_file_type(sample)
    if detected is None:
        return SignatureValidation(
            assessment=SignatureAssessment.UNKNOWN,
            expected_extension=expected,
            detected=None,
            reason="The file type could not be identified confidently from its signature.",
        )
    if detected.extension != expected:
        return SignatureValidation(
            assessment=SignatureAssessment.MISMATCH,
            expected_extension=expected,
            detected=detected,
            reason="The detected file type does not match the filename extension.",
        )
    return SignatureValidation(
        assessment=SignatureAssessment.MATCH,
        expected_extension=expected,
        detected=detected,
        reason="The file signature matches the normalized extension.",
    )


def assess_stored_signature(extension: str, mime_type: str) -> SignatureAssessment:
    """Reconstruct the magic-byte assessment from persisted metadata."""

    expected = extension.strip().casefold()
    normalized_mime = mime_type.strip().casefold()
    if normalized_mime == "application/octet-stream":
        return SignatureAssessment.UNKNOWN
    expected_mime = {
        ".exe": _PE.mime_type,
        ".msi": _MSI.mime_type,
        ".zip": _ZIP.mime_type,
        ".7z": _SEVEN_ZIP.mime_type,
    }.get(expected)
    if expected_mime is None or normalized_mime != expected_mime:
        return SignatureAssessment.MISMATCH
    return SignatureAssessment.MATCH
