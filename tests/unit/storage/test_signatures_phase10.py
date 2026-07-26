"""Magic-byte detection coverage for the Phase 10 allowlist."""

from app.storage.signatures import (
    SignatureAssessment,
    assess_stored_signature,
    detect_file_type,
    validate_file_signature,
)


def _pe_bytes() -> bytes:
    payload = bytearray(256)
    payload[:2] = b"MZ"
    payload[0x3C:0x40] = (128).to_bytes(4, "little")
    payload[128:132] = b"PE\x00\x00"
    return bytes(payload)


def test_detects_supported_signatures() -> None:
    samples = (
        (_pe_bytes(), ".exe"),
        (bytes.fromhex("D0CF11E0A1B11AE1") + b"x", ".msi"),
        (b"PK\x03\x04rest", ".zip"),
        (b"PK\x05\x06rest", ".zip"),
        (bytes.fromhex("377ABCAF271C") + b"rest", ".7z"),
    )
    for sample, expected in samples:
        detected = detect_file_type(sample)
        assert detected is not None
        assert detected.extension == expected


def test_rejects_truncated_or_fake_pe() -> None:
    assert detect_file_type(b"MZ") is None
    payload = bytearray(128)
    payload[:2] = b"MZ"
    payload[0x3C:0x40] = (120).to_bytes(4, "little")
    assert detect_file_type(bytes(payload)) is None


def test_signature_validation_match_mismatch_and_unknown() -> None:
    match = validate_file_signature(".zip", b"PK\x03\x04rest")
    mismatch = validate_file_signature(".exe", b"PK\x03\x04rest")
    unknown = validate_file_signature(".zip", b"not-an-archive")

    assert match.assessment is SignatureAssessment.MATCH
    assert match.detected is not None
    assert match.detected.mime_type == "application/zip"
    assert mismatch.assessment is SignatureAssessment.MISMATCH
    assert mismatch.detected is not None
    assert mismatch.detected.extension == ".zip"
    assert unknown.assessment is SignatureAssessment.UNKNOWN
    assert unknown.detected is None


def test_reconstructs_persisted_magic_assessment() -> None:
    assert assess_stored_signature(".zip", "application/zip") is SignatureAssessment.MATCH
    assert assess_stored_signature(".exe", "application/zip") is SignatureAssessment.MISMATCH
    assert (
        assess_stored_signature(".zip", "application/octet-stream") is SignatureAssessment.UNKNOWN
    )
    assert assess_stored_signature(".unknown", "application/zip") is SignatureAssessment.MISMATCH
