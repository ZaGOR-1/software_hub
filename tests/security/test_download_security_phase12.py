"""Security acceptance checks for X-Accel-backed downloads."""

from pathlib import Path

import pytest
from app.core.config import AppSettings
from pydantic import ValidationError


def test_internal_download_prefix_and_cookie_scope_are_hardened() -> None:
    settings = AppSettings(app_environment="test")
    assert settings.internal_download_prefix == "/protected-downloads/"
    assert settings.session_cookie_path == "/"

    with pytest.raises(ValidationError, match="cookie path"):
        AppSettings(app_environment="test", session_cookie_path="/admin")
    with pytest.raises(ValidationError, match="dedicated internal path"):
        AppSettings(app_environment="test", internal_download_prefix="/download/")


def test_nginx_internal_location_is_not_publicly_addressable() -> None:
    config = Path("nginx/conf.d/default.conf").read_text(encoding="utf-8")
    assert "location ^~ /protected-downloads/" in config
    assert "internal;" in config
    assert "alias /srv/software-hub/storage/software/;" in config
    assert "autoindex off;" in config
    assert "limit_req zone=download_requests" in config


def test_nginx_never_points_internal_downloads_at_quarantine() -> None:
    config = Path("nginx/conf.d/default.conf").read_text(encoding="utf-8")
    internal_block = config.split("location ^~ /protected-downloads/", 1)[1].split("}", 1)[0]
    assert "quarantine" not in internal_block
    assert "temporary" not in internal_block
