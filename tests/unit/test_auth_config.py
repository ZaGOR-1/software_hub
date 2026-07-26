"""Configuration invariants for authentication and session security."""

from typing import Any

import pytest
from app.core.config import AppSettings
from pydantic import ValidationError

PRODUCTION_VALUES: dict[str, Any] = {
    "app_environment": "production",
    "app_secret_key": "prod-app-secret-0123456789-ABCDEFGH",
    "csrf_secret": "prod-csrf-secret-9876543210-HGFEDCBA",
    "public_base_url": "https://software.hotzagor.tech",
    "trusted_hosts": ("software.hotzagor.tech",),
}


def test_cookie_secure_default_follows_environment() -> None:
    assert AppSettings(app_environment="test").effective_session_cookie_secure is False
    assert AppSettings(**PRODUCTION_VALUES).effective_session_cookie_secure is True
    assert (
        AppSettings(
            app_environment="test", session_cookie_secure=True
        ).effective_session_cookie_secure
        is True
    )


def test_session_timeout_relationships_are_validated() -> None:
    with pytest.raises(ValidationError, match="Absolute session lifetime"):
        AppSettings(session_idle_timeout_seconds=600, session_absolute_timeout_seconds=600)
    with pytest.raises(ValidationError, match="touch interval"):
        AppSettings(session_idle_timeout_seconds=60, session_touch_interval_seconds=60)
    with pytest.raises(ValidationError, match="password_max_length"):
        AppSettings(password_min_length=64, password_max_length=64)


def test_production_rejects_insecure_cookie_and_weak_argon2() -> None:
    with pytest.raises(ValidationError, match="Secure session cookies"):
        AppSettings(**PRODUCTION_VALUES, session_cookie_secure=False)
    with pytest.raises(ValidationError, match="Argon2 time"):
        AppSettings(**PRODUCTION_VALUES, argon2_time_cost=2)
    with pytest.raises(ValidationError, match="Argon2 memory"):
        AppSettings(**PRODUCTION_VALUES, argon2_memory_cost_kib=32_768)


def test_cookie_name_path_and_csrf_header_are_validated() -> None:
    with pytest.raises(ValidationError):
        AppSettings(session_cookie_name="bad cookie")
    with pytest.raises(ValidationError):
        AppSettings(session_cookie_path="admin")
    with pytest.raises(ValidationError, match="header name"):
        AppSettings(csrf_header_name="bad header")


def test_csrf_configuration_invariants(test_settings: AppSettings) -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        AppSettings(
            app_environment="test",
            app_secret_key="test-app-secret-0123456789-ABCDEFGH",
            csrf_secret="test-csrf-secret-9876543210-HGFEDCBA",
            database_url=test_settings.database_url,
            session_idle_timeout_seconds=1_800,
            session_absolute_timeout_seconds=3_600,
            csrf_token_ttl_seconds=7_200,
            argon2_time_cost=1,
            argon2_memory_cost_kib=1_024,
            argon2_parallelism=1,
        )

    with pytest.raises(ValidationError, match="different names"):
        AppSettings(
            app_environment="test",
            app_secret_key="test-app-secret-0123456789-ABCDEFGH",
            csrf_secret="test-csrf-secret-9876543210-HGFEDCBA",
            database_url=test_settings.database_url,
            login_csrf_cookie_name="same_cookie",
            session_cookie_name="same_cookie",
            argon2_time_cost=1,
            argon2_memory_cost_kib=1_024,
            argon2_parallelism=1,
        )
