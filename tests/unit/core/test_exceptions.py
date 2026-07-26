"""Tests for safe typed application exceptions."""

from app.core.exceptions import EntityNotFound, ErrorCode, StorageError


def test_application_error_carries_only_declared_safe_metadata() -> None:
    exc = EntityNotFound(
        "Software was not found.",
        headers={"X-Test": "value"},
        safe_metadata={"entity": "software"},
    )

    assert exc.status_code == 404
    assert exc.code is ErrorCode.NOT_FOUND
    assert exc.public_message == "Software was not found."
    assert exc.headers == {"X-Test": "value"}
    assert exc.safe_metadata == {"entity": "software"}
    assert str(exc) == "Software was not found."


def test_application_error_uses_safe_default_message() -> None:
    exc = StorageError()

    assert exc.status_code == 503
    assert exc.public_message == "File storage is temporarily unavailable."
