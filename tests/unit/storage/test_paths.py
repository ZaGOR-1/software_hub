"""Tests for private directory creation and path containment."""

import os
import stat
from pathlib import Path, PurePosixPath

import pytest
from app.core.constants import STORAGE_DIRECTORY_MODE
from app.core.exceptions import StorageError
from app.storage.paths import (
    ensure_private_directory,
    ensure_private_parent,
    relative_to_root,
    safe_resolve,
)


def test_ensure_private_directory_creates_and_hardens_permissions(tmp_path: Path) -> None:
    directory = tmp_path / "nested" / "private"
    resolved = ensure_private_directory(directory)

    assert resolved == directory.resolve()
    if os.name != "nt":
        assert stat.S_IMODE(directory.stat().st_mode) == STORAGE_DIRECTORY_MODE
    assert not list(directory.glob(".software-hub-write-probe-*"))


def test_ensure_private_directory_rejects_file_and_symlink(tmp_path: Path) -> None:
    regular_file = tmp_path / "file"
    regular_file.write_text("x")
    with pytest.raises(StorageError, match=r"symbolic links|not a real directory"):
        ensure_private_directory(regular_file)

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows symlink tests require Developer Mode or elevated privileges")
        raise
    with pytest.raises(StorageError, match=r"symbolic links|not a real directory"):
        ensure_private_directory(link)


@pytest.mark.parametrize(
    "relative",
    ["../escape", "a/../../escape", "/absolute", r"folder\file", "a/./file", "\x00"],
)
def test_safe_resolve_rejects_cross_platform_traversal(tmp_path: Path, relative: str) -> None:
    root = ensure_private_directory(tmp_path / "root")
    with pytest.raises(StorageError):
        safe_resolve(root, relative)


def test_safe_resolve_rejects_existing_symlink_escape(tmp_path: Path) -> None:
    root = ensure_private_directory(tmp_path / "root")
    outside = ensure_private_directory(tmp_path / "outside")
    try:
        (root / "alias").symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows symlink tests require Developer Mode or elevated privileges")
        raise

    with pytest.raises(StorageError, match="escapes"):
        safe_resolve(root, "alias/file.exe")


def test_safe_resolve_and_relative_to_root_round_trip(tmp_path: Path) -> None:
    root = ensure_private_directory(tmp_path / "root")
    candidate = safe_resolve(root, PurePosixPath("aa", "bb", "file.exe"))
    assert candidate == root / "aa" / "bb" / "file.exe"
    assert relative_to_root(candidate, root) == PurePosixPath("aa/bb/file.exe")

    with pytest.raises(StorageError, match="escapes"):
        relative_to_root(tmp_path / "outside", root)


def test_ensure_private_parent_creates_shards_without_symlinks(tmp_path: Path) -> None:
    root = ensure_private_directory(tmp_path / "root")
    parent = ensure_private_parent(root, "aa/bb/file.exe")

    assert parent == root / "aa" / "bb"
    if os.name != "nt":
        assert stat.S_IMODE(parent.stat().st_mode) == STORAGE_DIRECTORY_MODE

    outside = ensure_private_directory(tmp_path / "outside")
    try:
        (root / "cc").symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows symlink tests require Developer Mode or elevated privileges")
        raise
    with pytest.raises(StorageError):
        ensure_private_parent(root, "cc/dd/file.exe")
