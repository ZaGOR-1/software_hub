"""Tests for atomic storage moves and file permissions."""

import os
import stat
from pathlib import Path

import pytest
from app.core.constants import STORAGE_FILE_MODE
from app.core.exceptions import StorageError
from app.storage.move import atomic_move, harden_file_permissions
from app.storage.paths import ensure_private_directory


def test_atomic_move_creates_parent_and_removes_executable_bits(tmp_path: Path) -> None:
    source_root = ensure_private_directory(tmp_path / "temporary")
    destination_root = ensure_private_directory(tmp_path / "quarantine")
    source = source_root / "source.upload"
    source.write_bytes(b"payload")
    source.chmod(0o777)

    result = atomic_move(
        source_root=source_root,
        source_relative_path="source.upload",
        destination_root=destination_root,
        destination_relative_path="aa/bb/file.exe",
    )

    assert not source.exists()
    assert result.destination.read_bytes() == b"payload"
    assert result.size_bytes == 7
    if os.name != "nt":
        assert stat.S_IMODE(result.destination.stat().st_mode) == STORAGE_FILE_MODE


def test_atomic_move_refuses_overwrite_symlink_and_non_regular_source(tmp_path: Path) -> None:
    source_root = ensure_private_directory(tmp_path / "temporary")
    destination_root = ensure_private_directory(tmp_path / "quarantine")

    source = source_root / "source.upload"
    source.write_bytes(b"payload")
    destination = destination_root / "file.exe"
    destination.write_bytes(b"existing")
    with pytest.raises(StorageError, match="already exists"):
        atomic_move(
            source_root=source_root,
            source_relative_path="source.upload",
            destination_root=destination_root,
            destination_relative_path="file.exe",
        )

    target = source_root / "target"
    target.write_bytes(b"target")
    link = source_root / "link.upload"
    try:
        link.symlink_to(target)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows symlink tests require Developer Mode or elevated privileges")
        raise
    with pytest.raises(StorageError, match="Symbolic links"):
        atomic_move(
            source_root=source_root,
            source_relative_path="link.upload",
            destination_root=destination_root,
            destination_relative_path="other.exe",
        )

    directory = source_root / "directory.upload"
    directory.mkdir()
    with pytest.raises(StorageError, match="regular files"):
        harden_file_permissions(directory)


def test_atomic_move_rejects_cross_device_operation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_root = ensure_private_directory(tmp_path / "temporary")
    destination_root = ensure_private_directory(tmp_path / "quarantine")
    source = source_root / "source.upload"
    source.write_bytes(b"payload")

    original_stat = Path.stat

    def different_device(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        result = original_stat(path, follow_symlinks=follow_symlinks)
        if path == destination_root:
            values = list(result)
            values[2] = result.st_dev + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(Path, "stat", different_device)
    with pytest.raises(StorageError, match="same filesystem"):
        atomic_move(
            source_root=source_root,
            source_relative_path="source.upload",
            destination_root=destination_root,
            destination_relative_path="file.exe",
        )
