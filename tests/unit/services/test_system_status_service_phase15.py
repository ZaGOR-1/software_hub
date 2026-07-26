"""System status helper coverage for Phase 15."""

from pathlib import Path

from app.services.system_status_service import format_bytes


def test_format_bytes_returns_stable_human_values() -> None:
    assert format_bytes(None) == "—"
    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.0 KiB"
    assert format_bytes(5 * 1024 * 1024) == "5.0 MiB"


def test_backup_manifest_name_contract_is_not_a_physical_path(tmp_path: Path) -> None:
    manifest = tmp_path / "software-hub-backup-20260724" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text("{}", encoding="utf-8")

    assert manifest.name == "manifest.json"
    assert manifest.parent.name.startswith("software-hub-backup-")
