"""Tests for the minimal Phase 1 settings object."""

import pytest
from app.core.config import AppSettings
from pydantic import ValidationError


def test_settings_have_safe_bootstrap_defaults() -> None:
    settings = AppSettings(_env_file=None)

    assert settings.app_name == "Software Hub"
    assert settings.app_environment == "development"
    assert settings.app_debug is False
    assert settings.health_path == "/health"


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(app_environment="staging")


def test_invalid_health_path_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(health_path="health")
