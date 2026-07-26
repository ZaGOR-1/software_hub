"""Tests for conservative temporary cleanup."""

import os
from pathlib import Path

import pytest
from app.core.exceptions import StorageError
from app.storage.cleanup import cleanup_temporary_files
from app.storage.filename import generate_temporary_filename


def _set_age(path: Path, *, timestamp: float) -> None:
    os.utime(path, (timestamp, timestamp))


def test_cleanup_dry_run_and_delete_only_generated_stale_files(tmp_path: Path) -> None:
    root = tmp_path / "temporary"
    nested = root / "nested"
    nested.mkdir(parents=True)
    now = 100_000.0

    stale = root / generate_temporary_filename()
    stale.write_bytes(b"old")
    _set_age(stale, timestamp=now - 10_000)

    fresh = nested / generate_temporary_filename()
    fresh.write_bytes(b"fresh")
    _set_age(fresh, timestamp=now - 10)

    manual = root / "manual.upload"
    manual.write_bytes(b"operator")
    _set_age(manual, timestamp=now - 10_000)

    target = root / "target"
    target.write_bytes(b"target")
    link = root / generate_temporary_filename()
    try:
        link.symlink_to(target)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows symlink tests require Developer Mode or elevated privileges")
        raise

    dry_run = cleanup_temporary_files(
        root,
        max_age_seconds=3_600,
        dry_run=True,
        now_timestamp=now,
    )
    assert dry_run.eligible == 1
    assert dry_run.deleted == 0
    assert stale.exists()

    report = cleanup_temporary_files(
        root,
        max_age_seconds=3_600,
        dry_run=False,
        now_timestamp=now,
    )
    assert report.deleted == 1
    assert report.reclaimed_bytes == 3
    assert not stale.exists()
    assert fresh.exists()
    assert manual.exists()
    assert link.is_symlink()


def test_cleanup_validates_arguments_and_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        cleanup_temporary_files(tmp_path, max_age_seconds=0)
    with pytest.raises(StorageError, match="unavailable"):
        cleanup_temporary_files(tmp_path / "missing", max_age_seconds=60)
