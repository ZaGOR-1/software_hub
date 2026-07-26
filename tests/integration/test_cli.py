"""Tests for maintenance CLI commands and password handling."""

import json
import os
from pathlib import Path

import pytest
from app.cli import _read_password, build_parser, main
from app.core.config import get_settings
from app.database.migrations_helpers import upgrade_database
from app.database.session import create_database
from app.models.session import UserSession
from app.models.user import User


def configure_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("SOFTWARE_HUB_APP_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "SOFTWARE_HUB_APP_SECRET_KEY",
        "test-app-secret-0123456789-ABCDEFGH",
    )
    monkeypatch.setenv(
        "SOFTWARE_HUB_CSRF_SECRET",
        "test-csrf-secret-9876543210-HGFEDCBA",
    )
    monkeypatch.setenv("SOFTWARE_HUB_DATABASE_URL", database_url)
    monkeypatch.setenv("SOFTWARE_HUB_ARGON2_TIME_COST", "1")
    monkeypatch.setenv("SOFTWARE_HUB_ARGON2_MEMORY_COST_KIB", "1024")
    monkeypatch.setenv("SOFTWARE_HUB_ARGON2_PARALLELISM", "1")
    monkeypatch.setenv("SOFTWARE_HUB_ADMIN_PASSWORD", "correct horse battery staple")
    get_settings.cache_clear()
    upgrade_database(database_url)
    return database_url


def test_parser_never_accepts_plain_password_argument() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "--password" not in help_text
    assert "create-admin" in help_text


def test_create_change_revoke_and_cleanup_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_url = configure_cli(monkeypatch, tmp_path)
    assert main(["create-admin", "--username", "admin"]) == 0
    assert "created" in capsys.readouterr().out

    assert main(["create-admin", "--username", "admin"]) == 1
    assert "Error:" in capsys.readouterr().err

    monkeypatch.setenv("SOFTWARE_HUB_ADMIN_PASSWORD", "new strong password value")
    assert main(["change-admin-password", "--username", "admin"]) == 0
    assert "active sessions revoked" in capsys.readouterr().out
    assert main(["revoke-sessions", "--username", "admin"]) == 0
    assert main(["cleanup-expired-sessions"]) == 0

    settings = get_settings()
    database = create_database(settings)
    try:
        with database.session() as session:
            assert session.query(User).filter_by(username="admin").count() == 1
            assert session.query(UserSession).count() == 0
    finally:
        database.dispose()
    assert database_url.endswith("cli.db")


def test_read_password_uses_environment_or_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUSTOM_PASSWORD", "from-environment")
    assert _read_password("CUSTOM_PASSWORD") == "from-environment"

    monkeypatch.delenv("CUSTOM_PASSWORD")
    answers = iter(["one password value", "different password"])
    monkeypatch.setattr("getpass.getpass", lambda _prompt: next(answers))
    with pytest.raises(ValueError, match="do not match"):
        _read_password("CUSTOM_PASSWORD")


def configure_phase16_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    """Configure migrated database and private roots for maintenance commands."""

    database_url = configure_cli(monkeypatch, tmp_path)
    storage = tmp_path / "storage"
    monkeypatch.setenv("SOFTWARE_HUB_STORAGE_ROOT", str(storage))
    monkeypatch.setenv("SOFTWARE_HUB_TEMPORARY_ROOT", str(storage / "temporary"))
    monkeypatch.setenv("SOFTWARE_HUB_QUARANTINE_ROOT", str(storage / "quarantine"))
    monkeypatch.setenv("SOFTWARE_HUB_ICONS_ROOT", str(storage / "icons"))
    monkeypatch.setenv("SOFTWARE_HUB_BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setenv("SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES", "0")
    monkeypatch.setenv("SOFTWARE_HUB_BACKUP_MIN_FREE_BYTES", "0")
    monkeypatch.setenv("SOFTWARE_HUB_BACKUP_RETENTION_COUNT", "2")
    get_settings.cache_clear()
    return database_url


def test_phase16_cli_backup_storage_and_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_phase16_cli(monkeypatch, tmp_path)

    assert main(["create-backup"]) == 0
    created = json.loads(capsys.readouterr().out)
    backup_id = created["backup_id"]
    assert backup_id.startswith("software-hub-backup-")

    assert main(["list-backups"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["backup_id"] == backup_id

    assert main(["verify-backup", "--backup-id", backup_id]) == 0
    assert json.loads(capsys.readouterr().out)["checksum_verified"] is True

    assert main(["verify-storage"]) == 0
    assert json.loads(capsys.readouterr().out)["issues"] == []
    assert main(["show-system-status"]) == 0
    assert json.loads(capsys.readouterr().out)["database"]["state"] == "ok"

    assert main(["restore-backup", "--backup-id", backup_id]) == 1
    assert "requires --yes" in capsys.readouterr().err
    assert main(["cleanup-backups", "--apply"]) == 1
    assert "requires --yes" in capsys.readouterr().err
    assert main(["recalculate-checksums", "--apply"]) == 1
    assert "requires --yes" in capsys.readouterr().err
    assert main(["find-orphan-files", "--delete"]) == 1
    assert "requires --yes" in capsys.readouterr().err


def test_phase16_cli_temporary_and_orphan_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_phase16_cli(monkeypatch, tmp_path)
    settings = get_settings()
    storage = settings.temporary_root
    storage.mkdir(mode=0o750, parents=True)
    stale = storage / ("1" * 32 + ".upload")
    stale.write_bytes(b"stale")
    os.utime(stale, (1, 1))

    assert main(["cleanup-temporary-files"]) == 0
    assert json.loads(capsys.readouterr().out)["eligible"] == 1
    assert stale.exists()
    assert main(["cleanup-temporary-files", "--apply", "--yes"]) == 0
    assert json.loads(capsys.readouterr().out)["deleted"] == 1
    assert not stale.exists()

    orphan = settings.quarantine_root / "orphan.zip"
    orphan.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan")
    assert main(["find-orphan-files"]) == 0
    assert len(json.loads(capsys.readouterr().out)["discovered"]) == 1
    assert main(["find-orphan-files", "--delete", "--yes"]) == 0
    assert json.loads(capsys.readouterr().out)["deleted_count"] == 1
    assert not orphan.exists()
