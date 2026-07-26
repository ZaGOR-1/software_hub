"""Tests for server-generated Phase-9 upload path plans."""

from pathlib import Path

from app.core.config import AppSettings
from app.storage.paths import StoragePaths, ensure_private_directory
from app.storage.upload import plan_upload_paths


def test_upload_plan_never_uses_original_filename_as_a_path(tmp_path: Path) -> None:
    settings = AppSettings(
        _env_file=None,
        storage_root=tmp_path / "storage",
        temporary_root=tmp_path / "storage" / "temporary",
        quarantine_root=tmp_path / "storage" / "quarantine",
        icons_root=tmp_path / "storage" / "icons",
        backup_root=tmp_path / "backups",
        storage_min_free_bytes=0,
    )
    paths = StoragePaths.from_settings(settings)
    for directory in paths.required_directories():
        ensure_private_directory(directory)

    plan = plan_upload_paths("My Useful Tool 2.0.exe", settings=settings, paths=paths)

    assert plan.original.value == "My Useful Tool 2.0.exe"
    assert "My Useful Tool" not in str(plan.temporary_path)
    assert "My Useful Tool" not in str(plan.quarantine_path)
    assert "My Useful Tool" not in str(plan.permanent_path)
    assert plan.storage_filename in str(plan.quarantine_path)
    assert plan.storage_filename in str(plan.permanent_path)
    assert plan.quarantine_relative_path == plan.permanent_relative_path
