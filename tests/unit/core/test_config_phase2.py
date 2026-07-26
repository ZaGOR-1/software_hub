"""Fail-fast and normalization tests for Phase 2 settings."""

from pathlib import Path
from typing import Any

import pytest
from app.core.config import AppSettings
from app.core.constants import GIBIBYTE
from app.core.enums import AppEnvironment
from pydantic import ValidationError

APP_SECRET = "App-secret-2026-with-high-entropy-A9x7Q2mK"
CSRF_SECRET = "Csrf-secret-2026-with-high-entropy-B8v6P1nJ"


def production_settings(**overrides: object) -> AppSettings:
    values: dict[str, Any] = {
        "app_environment": AppEnvironment.PRODUCTION,
        "app_secret_key": APP_SECRET,
        "csrf_secret": CSRF_SECRET,
        "public_base_url": "https://software.hotzagor.tech",
        "trusted_hosts": ("software.hotzagor.tech",),
        "docs_enabled": False,
    }
    values.update(overrides)
    return AppSettings(_env_file=None, **values)


def test_production_settings_accept_secure_configuration() -> None:
    settings = production_settings()

    assert settings.is_production is True
    assert settings.public_base_url.scheme == "https"
    assert settings.trusted_hosts == ("software.hotzagor.tech",)


@pytest.mark.parametrize("missing_field", ["app_secret_key", "csrf_secret"])
def test_production_requires_both_secrets(missing_field: str) -> None:
    with pytest.raises(ValidationError, match="Production requires"):
        production_settings(**{missing_field: None})


@pytest.mark.parametrize("field", ["app_secret_key", "csrf_secret"])
def test_weak_secrets_are_rejected_in_all_environments(field: str) -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        AppSettings.model_validate({field: "too-short"})


def test_predictable_long_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="too predictable"):
        AppSettings(_env_file=None, app_secret_key="a" * 64)


def test_secrets_must_be_different() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        AppSettings(
            _env_file=None,
            app_secret_key=APP_SECRET,
            csrf_secret=APP_SECRET,
        )


def test_debug_is_forbidden_in_production() -> None:
    with pytest.raises(ValidationError, match="Debug mode"):
        production_settings(app_debug=True)


def test_production_requires_https() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        production_settings(public_base_url="http://software.hotzagor.tech")


def test_production_rejects_wildcard_host() -> None:
    with pytest.raises(ValidationError, match="Wildcard"):
        production_settings(trusted_hosts=("*",))


def test_production_public_host_must_be_trusted() -> None:
    with pytest.raises(ValidationError, match="must be included"):
        production_settings(trusted_hosts=("admin.hotzagor.tech",))


def test_csv_settings_are_normalized_and_deduplicated() -> None:
    settings = AppSettings(
        _env_file=None,
        trusted_hosts="LOCALHOST, localhost, software.hotzagor.tech",
        trusted_proxy_networks="127.0.0.1, 10.0.0.4/24",
        allowed_extensions="EXE, .zip, exe",
    )

    assert settings.trusted_hosts == ("localhost", "software.hotzagor.tech")
    assert settings.trusted_proxy_networks == ("127.0.0.1/32", "10.0.0.0/24")
    assert settings.allowed_extensions == (".exe", ".zip")


@pytest.mark.parametrize(
    "value",
    [(), "https://example.com", "bad host", "foo/bar", "foo*bar.example"],
)
def test_invalid_trusted_hosts_are_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        AppSettings.model_validate({"trusted_hosts": value})


def test_invalid_proxy_network_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Invalid trusted proxy network"):
        AppSettings(_env_file=None, trusted_proxy_networks=("not-a-network",))


@pytest.mark.parametrize("extension", [".", ".tar.gz", "bad/name", "tool!"])
def test_invalid_extensions_are_rejected(extension: str) -> None:
    with pytest.raises(ValidationError, match="Invalid file extension"):
        AppSettings(_env_file=None, allowed_extensions=(extension,))


def test_empty_extensions_are_rejected() -> None:
    with pytest.raises(ValidationError, match="At least one upload extension"):
        AppSettings(_env_file=None, allowed_extensions=())


@pytest.mark.parametrize(
    "field",
    ["storage_root", "temporary_root", "quarantine_root", "icons_root", "backup_root"],
)
def test_storage_paths_must_be_absolute(field: str) -> None:
    with pytest.raises(ValidationError, match="must be absolute"):
        AppSettings.model_validate({field: Path("relative/path")})


def test_upload_size_is_bounded() -> None:
    assert AppSettings(_env_file=None).max_upload_size == 2 * GIBIBYTE

    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, max_upload_size=100)


def test_request_header_and_csp_reject_header_injection() -> None:
    with pytest.raises(ValidationError, match="valid HTTP header"):
        AppSettings(_env_file=None, request_id_header="Bad Header")

    with pytest.raises(ValidationError, match="line breaks"):
        AppSettings(_env_file=None, content_security_policy="default-src 'self'\r\nInjected: x")


def test_storage_subdirectories_must_be_distinct_and_contained(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    common = storage / "common"
    with pytest.raises(ValidationError, match="must be distinct"):
        AppSettings(
            _env_file=None,
            storage_root=storage,
            temporary_root=common,
            quarantine_root=common,
            icons_root=storage / "icons",
            backup_root=tmp_path / "backups",
        )

    with pytest.raises(ValidationError, match="must be descendants"):
        AppSettings(
            _env_file=None,
            storage_root=storage,
            temporary_root=tmp_path / "outside",
            quarantine_root=storage / "quarantine",
            icons_root=storage / "icons",
            backup_root=tmp_path / "backups",
        )


def test_backup_root_cannot_be_exposed_inside_storage(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    with pytest.raises(ValidationError, match="outside storage_root"):
        AppSettings(
            _env_file=None,
            storage_root=storage,
            temporary_root=storage / "temporary",
            quarantine_root=storage / "quarantine",
            icons_root=storage / "icons",
            backup_root=storage / "backups",
        )


def test_storage_capacity_and_cleanup_age_are_bounded() -> None:
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, storage_min_free_bytes=-1)
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, temporary_file_max_age_seconds=60)


def test_backup_storage_and_database_roots_must_be_disjoint(tmp_path: Path) -> None:
    storage = tmp_path / "data" / "storage"
    with pytest.raises(ValueError, match="disjoint"):
        AppSettings(
            storage_root=storage,
            temporary_root=storage / "temporary",
            quarantine_root=storage / "quarantine",
            icons_root=storage / "icons",
            backup_root=tmp_path / "data",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'database.db'}",
        )

    backup = tmp_path / "backups"
    with pytest.raises(ValueError, match="database"):
        AppSettings(
            storage_root=storage,
            temporary_root=storage / "temporary",
            quarantine_root=storage / "quarantine",
            icons_root=storage / "icons",
            backup_root=backup,
            database_url=f"sqlite+pysqlite:///{backup / 'database.db'}",
        )


def test_backup_retention_settings_are_bounded(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="greater than or equal"):
        AppSettings(
            backup_retention_count=0,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'database.db'}",
            storage_root=tmp_path / "storage",
            temporary_root=tmp_path / "storage" / "temporary",
            quarantine_root=tmp_path / "storage" / "quarantine",
            icons_root=tmp_path / "storage" / "icons",
            backup_root=tmp_path / "backups",
        )
