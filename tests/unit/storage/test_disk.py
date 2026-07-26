"""Tests for storage capacity guards."""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.core.exceptions import StorageError
from app.storage import disk


def test_get_and_require_disk_space(tmp_path: Path) -> None:
    snapshot = disk.get_disk_space(tmp_path)
    assert snapshot.total > 0
    assert snapshot.free >= 0
    assert disk.ensure_free_space(tmp_path, required_bytes=0, reserve_bytes=0) == snapshot


def test_free_space_guard_reserves_capacity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1_000, used=600, free=400),
    )

    with pytest.raises(StorageError, match="Insufficient free space") as captured:
        disk.ensure_free_space(tmp_path, required_bytes=250, reserve_bytes=200)

    assert captured.value.safe_metadata == {
        "required_bytes": 250,
        "reserve_bytes": 200,
        "free_bytes": 400,
    }


@pytest.mark.parametrize(("required", "reserve"), [(-1, 0), (0, -1)])
def test_negative_capacity_requirements_are_programming_errors(
    tmp_path: Path,
    required: int,
    reserve: int,
) -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        disk.ensure_free_space(tmp_path, required_bytes=required, reserve_bytes=reserve)


def test_disk_usage_failure_is_wrapped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail(_path: Path) -> None:
        raise OSError("device unavailable")

    monkeypatch.setattr(shutil, "disk_usage", fail)
    with pytest.raises(StorageError, match="could not be determined"):
        disk.get_disk_space(tmp_path)
