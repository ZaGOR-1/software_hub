"""Tests for Phase 3 database configuration invariants."""

from pathlib import Path

import pytest
from app.core.config import AppSettings
from pydantic import ValidationError


@pytest.mark.parametrize(
    "database_url",
    ["not a url", "postgresql://localhost/software_hub", "sqlite+pysqlite://"],
)
def test_database_url_rejects_invalid_or_unsupported_values(database_url: str) -> None:
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, database_url=database_url)


def production_values(database_url: str) -> dict[str, object]:
    return {
        "app_environment": "production",
        "app_secret_key": "App-secret-2026-with-high-entropy-A9x7Q2mK",
        "csrf_secret": "Csrf-secret-2026-with-high-entropy-B8v6P1nJ",
        "public_base_url": "https://software.hotzagor.tech",
        "trusted_hosts": ("software.hotzagor.tech",),
        "database_url": database_url,
    }


@pytest.mark.parametrize(
    "database_url",
    ["sqlite+pysqlite:///:memory:", "sqlite+pysqlite:///relative.db"],
)
def test_production_requires_persistent_absolute_database_path(database_url: str) -> None:
    with pytest.raises(ValidationError):
        AppSettings(_env_file=None, **production_values(database_url))  # type: ignore[arg-type]


def test_production_accepts_absolute_sqlite_path(tmp_path: Path) -> None:
    settings = AppSettings(
        _env_file=None,
        **production_values(f"sqlite+pysqlite:///{tmp_path / 'production.db'}"),  # type: ignore[arg-type]
    )

    assert settings.database_url.endswith("production.db")
    assert settings.sqlite_busy_timeout_ms == 5000
    assert settings.sqlite_synchronous_mode.value == "NORMAL"
