"""Strict audit metadata allowlist coverage for Phase 15."""

from app.services.audit_service import sanitize_audit_metadata


def test_audit_metadata_uses_flat_allowlist_and_bounded_values() -> None:
    long_reason = "x" * 400
    cleaned = sanitize_audit_metadata(
        {
            "reason": long_reason,
            "release_id": 42,
            "physical_file_preserved": True,
            "scanner_status": ["clean", "unavailable"],
            "password": "must-not-persist",
            "session_token": "must-not-persist",
            "relative_storage_path": "/srv/software-hub/private/file.zip",
            "slug": {"nested_secret": "must-not-persist"},
            "unknown": "drop-me",
        }
    )

    assert cleaned == {
        "reason": "x" * 256,
        "release_id": 42,
        "physical_file_preserved": True,
        "scanner_status": ["clean", "unavailable"],
    }
    serialized = repr(cleaned)
    assert "must-not-persist" not in serialized
    assert "/srv/software-hub" not in serialized


def test_audit_metadata_rejects_non_finite_and_unsupported_values() -> None:
    assert sanitize_audit_metadata(
        {
            "file_size_bytes": float("inf"),
            "reason": object(),
            "duplicate_count": 3,
        }
    ) == {"duplicate_count": 3}
