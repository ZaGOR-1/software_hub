"""Phase 10 upload configuration invariants."""

import pytest
from app.core.config import AppSettings
from pydantic import ValidationError as PydanticValidationError


def test_clamav_command_rejects_whitespace_and_control_characters() -> None:
    for value in ("clam scan", "clamscan\n--bad", ""):
        with pytest.raises(PydanticValidationError):
            AppSettings(clamav_command=value)


def test_upload_configuration_accepts_bounded_values() -> None:
    settings = AppSettings(
        upload_chunk_size=64 * 1024,
        upload_magic_sample_size=64,
        clamav_enabled=True,
        clamav_command="/usr/bin/clamscan",
        clamav_timeout_seconds=30,
    )
    assert settings.upload_chunk_size == 64 * 1024
    assert settings.upload_magic_sample_size == 64
    assert settings.clamav_enabled is True
