"""Upload validation facade for filenames, signatures and display metadata."""

from app.core.exceptions import FileValidationError
from app.storage.filename import NormalizedFilename, normalize_original_filename
from app.storage.signatures import (
    DetectedFileType,
    SignatureAssessment,
    SignatureValidation,
    assess_stored_signature,
    detect_file_type,
    validate_file_signature,
)


def normalize_display_filename(
    display_filename: str | None,
    *,
    original: NormalizedFilename,
    allowed_extensions: tuple[str, ...],
) -> str:
    """Validate an optional user-facing download name against the real extension."""

    if display_filename is None or not display_filename.strip():
        return original.value
    normalized = normalize_original_filename(
        display_filename,
        allowed_extensions=allowed_extensions,
    )
    if normalized.extension != original.extension:
        raise FileValidationError("The display filename must keep the uploaded extension.")
    return normalized.value


__all__ = [
    "DetectedFileType",
    "NormalizedFilename",
    "SignatureAssessment",
    "SignatureValidation",
    "assess_stored_signature",
    "detect_file_type",
    "normalize_display_filename",
    "normalize_original_filename",
    "validate_file_signature",
]
