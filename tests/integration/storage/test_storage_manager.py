"""Integration tests for startup storage readiness."""

import os
import stat
from pathlib import Path

import pytest
from app.core.config import AppSettings
from app.core.constants import STORAGE_DIRECTORY_MODE
from app.core.exceptions import StorageError
from app.main import create_app
from app.storage.manager import StorageManager
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_application_lifespan_initializes_all_private_storage(
    application: FastAPI,
    test_settings: AppSettings,
) -> None:
    manager = application.state.storage
    assert isinstance(manager, StorageManager)
    assert bool(manager.initialized) is False

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        assert bool(manager.initialized) is True
        for directory in manager.paths.required_directories():
            assert directory.is_dir()
            if os.name != "nt":
                assert stat.S_IMODE(directory.stat().st_mode) == STORAGE_DIRECTORY_MODE

    assert test_settings.storage_root.exists()


def test_storage_manager_cleanup_delegates_to_safe_cleanup(test_settings: AppSettings) -> None:
    manager = StorageManager.from_settings(test_settings)
    manager.initialize()
    report = manager.cleanup_temporary(dry_run=True)
    assert report.examined == 0


def test_startup_fails_for_symlinked_managed_directory(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    real_icons = storage / "real-icons"
    real_icons.mkdir()
    icons = storage / "icons"
    try:
        icons.symlink_to(real_icons, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows symlink tests require Developer Mode or elevated privileges")
        raise
    settings = AppSettings(
        _env_file=None,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'db.sqlite'}",
        storage_root=storage,
        temporary_root=storage / "temporary",
        quarantine_root=storage / "quarantine",
        icons_root=icons,
        backup_root=tmp_path / "backups",
        storage_min_free_bytes=0,
    )
    application = create_app(settings)

    with (
        pytest.raises(StorageError, match=r"symbolic links|not a real directory"),
        TestClient(application),
    ):
        pass


def test_storage_manager_fails_startup_when_reserve_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: AppSettings,
) -> None:
    manager = StorageManager.from_settings(test_settings)

    def fail_capacity(*_args: object, **_kwargs: object) -> None:
        raise StorageError("Insufficient free space is available for this file operation.")

    monkeypatch.setattr("app.storage.manager.ensure_free_space", fail_capacity)
    with pytest.raises(StorageError, match="Insufficient free space"):
        manager.initialize()
    assert manager.initialized is False
