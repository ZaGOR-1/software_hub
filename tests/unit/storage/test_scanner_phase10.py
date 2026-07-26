"""Optional scanner adapter tests without requiring ClamAV."""

import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import pytest
from app.core.config import AppSettings
from app.models.enums import ScannerStatus
from app.storage.scanner import (
    ClamAVCommandScanner,
    UnavailableScanner,
    create_file_scanner,
)


def _completed_process(returncode: int) -> Callable[..., SimpleNamespace]:
    def fake_run(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=returncode)

    return fake_run


def _raise_file_not_found(*_args: object, **_kwargs: object) -> NoReturn:
    raise FileNotFoundError


def _raise_timeout(*_args: object, **_kwargs: object) -> NoReturn:
    raise subprocess.TimeoutExpired("clam", 10)


def _raise_os_error(*_args: object, **_kwargs: object) -> NoReturn:
    raise OSError


def test_unavailable_scanner_and_factory(test_settings: AppSettings, tmp_path: Path) -> None:
    scanner = create_file_scanner(test_settings)
    result = scanner.scan(tmp_path / "missing")
    assert isinstance(scanner, UnavailableScanner)
    assert result.status is ScannerStatus.UNAVAILABLE


def test_clamav_exit_codes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "sample.zip"
    path.write_bytes(b"PK\x03\x04")
    scanner = ClamAVCommandScanner("clamscan", 10)

    for returncode, expected in (
        (0, ScannerStatus.CLEAN),
        (1, ScannerStatus.INFECTED),
        (2, ScannerStatus.ERROR),
    ):
        monkeypatch.setattr(subprocess, "run", _completed_process(returncode))
        assert scanner.scan(path).status is expected


def test_clamav_unavailable_timeout_and_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.zip"
    scanner = ClamAVCommandScanner("clamscan", 10)

    monkeypatch.setattr(subprocess, "run", _raise_file_not_found)
    assert scanner.scan(path).status is ScannerStatus.UNAVAILABLE

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    assert scanner.scan(path).status is ScannerStatus.ERROR

    monkeypatch.setattr(subprocess, "run", _raise_os_error)
    assert scanner.scan(path).status is ScannerStatus.ERROR


def test_enabled_scanner_factory(test_settings: AppSettings) -> None:
    settings = test_settings.model_copy(
        update={"clamav_enabled": True, "clamav_command": "/usr/bin/clamscan"}
    )
    scanner = create_file_scanner(settings)
    assert isinstance(scanner, ClamAVCommandScanner)
    assert scanner.command == "/usr/bin/clamscan"
