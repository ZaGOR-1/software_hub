"""Maintenance command-line interface for administrators and operators."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from app.core.config import AppSettings, get_settings
from app.core.exceptions import ApplicationError
from app.database.session import create_database
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.reconciliation_service import ReconciliationService
from app.services.session_service import SessionService
from app.services.system_status_service import SystemStatusService
from app.storage.manager import StorageManager

_DEFAULT_PASSWORD_ENV = "SOFTWARE_HUB_ADMIN_PASSWORD"  # nosec B105  # noqa: S105


def _read_password(environment_name: str) -> str:
    value = os.environ.get(environment_name)
    if value is not None:
        return value
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise ValueError("Passwords do not match.")
    return first


def _add_yes_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the explicitly destructive action.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the documented maintenance CLI without accepting passwords as arguments."""

    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin = subparsers.add_parser("create-admin", help="Create an administrator.")
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument("--password-env", default=_DEFAULT_PASSWORD_ENV)
    create_admin.add_argument("--no-superuser", action="store_true")

    change_password = subparsers.add_parser(
        "change-admin-password",
        help="Change an administrator password and revoke active sessions.",
    )
    change_password.add_argument("--username", required=True)
    change_password.add_argument("--password-env", default=_DEFAULT_PASSWORD_ENV)

    revoke = subparsers.add_parser("revoke-sessions", help="Revoke all sessions for a user.")
    revoke.add_argument("--username", required=True)

    subparsers.add_parser(
        "cleanup-expired-sessions",
        help="Delete sessions past idle or absolute expiration.",
    )

    subparsers.add_parser("create-backup", help="Create and verify a complete backup.")
    subparsers.add_parser("list-backups", help="List verified backups.")
    verify_backup = subparsers.add_parser(
        "verify-backup",
        help="Verify one backup manifest, all files and SQLite integrity.",
    )
    verify_backup.add_argument("--backup-id", required=True)

    cleanup_backups = subparsers.add_parser(
        "cleanup-backups",
        help="Dry-run backup retention or delete eligible old backups.",
    )
    cleanup_backups.add_argument("--apply", action="store_true")
    _add_yes_argument(cleanup_backups)

    restore = subparsers.add_parser(
        "restore-backup",
        help="Restore a verified backup while the application is stopped.",
    )
    restore.add_argument("--backup-id", required=True)
    restore.add_argument("--no-safety-backup", action="store_true")
    _add_yes_argument(restore)

    cleanup_temporary = subparsers.add_parser(
        "cleanup-temporary-files",
        help="Dry-run cleanup or delete stale generated upload files.",
    )
    cleanup_temporary.add_argument("--apply", action="store_true")
    _add_yes_argument(cleanup_temporary)

    verify_storage = subparsers.add_parser(
        "verify-storage",
        help="Compare SQLite metadata with private storage.",
    )
    verify_storage.add_argument("--skip-checksums", action="store_true")

    recalculate = subparsers.add_parser(
        "recalculate-checksums",
        help="Dry-run or explicitly update file checksums from physical bytes.",
    )
    recalculate.add_argument("--apply", action="store_true")
    recalculate.add_argument("--include-published", action="store_true")
    _add_yes_argument(recalculate)

    orphans = subparsers.add_parser(
        "find-orphan-files",
        help="List or explicitly delete files without database metadata.",
    )
    orphans.add_argument("--delete", action="store_true")
    _add_yes_argument(orphans)

    subparsers.add_parser(
        "show-system-status",
        help="Show database, storage, disk and latest-backup status.",
    )
    return parser


def _require_confirmation(args: argparse.Namespace, *, destructive: bool) -> None:
    if destructive and not bool(getattr(args, "yes", False)):
        raise ValueError("Destructive action requires --yes.")


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _serialize(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, sort_keys=True)


def _run_auth_command(args: argparse.Namespace, settings: AppSettings) -> str:
    database = create_database(settings)
    try:
        auth = AuthService(database, settings)
        if args.command == "create-admin":
            password = _read_password(args.password_env)
            user = auth.create_admin(
                username=args.username,
                password=password,
                is_superuser=not args.no_superuser,
            )
            return f"Administrator '{user.username}' created."
        if args.command == "change-admin-password":
            password = _read_password(args.password_env)
            user = auth.change_password(username=args.username, new_password=password)
            return f"Password changed for '{user.username}'; active sessions revoked."
        if args.command == "revoke-sessions":
            count = auth.revoke_sessions(username=args.username)
            return f"Revoked sessions: {count}."
        count = SessionService(database, settings).cleanup_expired(request_id="cli")
        return f"Deleted expired sessions: {count}."
    finally:
        database.dispose()


def _run_backup_command(args: argparse.Namespace, settings: AppSettings) -> str:
    service = BackupService(settings)
    if args.command == "create-backup":
        return _serialize(service.create_backup())
    if args.command == "list-backups":
        return _serialize(service.list_backups())
    if args.command == "verify-backup":
        return _serialize(service.verify_backup(args.backup_id))
    if args.command == "cleanup-backups":
        destructive = bool(args.apply)
        _require_confirmation(args, destructive=destructive)
        return _serialize(service.apply_retention(dry_run=not destructive))
    _require_confirmation(args, destructive=True)
    return _serialize(
        service.restore_backup(
            args.backup_id,
            create_safety_backup=not args.no_safety_backup,
        )
    )


def _run_storage_command(args: argparse.Namespace, settings: AppSettings) -> str:
    storage = StorageManager.from_settings(settings)
    storage.initialize()
    if args.command == "cleanup-temporary-files":
        destructive = bool(args.apply)
        _require_confirmation(args, destructive=destructive)
        return _serialize(storage.cleanup_temporary(dry_run=not destructive))

    database = create_database(settings)
    try:
        if args.command == "show-system-status":
            return _serialize(SystemStatusService(database, storage).snapshot())
        service = ReconciliationService(database, storage)
        if args.command == "verify-storage":
            return _serialize(service.verify_storage(verify_checksums=not args.skip_checksums))
        if args.command == "recalculate-checksums":
            destructive = bool(args.apply)
            _require_confirmation(args, destructive=destructive)
            return _serialize(
                service.recalculate_checksums(
                    dry_run=not destructive,
                    include_published=bool(args.include_published),
                )
            )
        destructive = bool(args.delete)
        _require_confirmation(args, destructive=destructive)
        return _serialize(service.cleanup_orphans(dry_run=not destructive))
    finally:
        database.dispose()


def _run(args: argparse.Namespace, settings: AppSettings) -> str:
    if args.command in {
        "create-admin",
        "change-admin-password",
        "revoke-sessions",
        "cleanup-expired-sessions",
    }:
        return _run_auth_command(args, settings)
    if args.command in {
        "create-backup",
        "list-backups",
        "verify-backup",
        "cleanup-backups",
        "restore-backup",
    }:
        return _run_backup_command(args, settings)
    if args.command in {
        "cleanup-temporary-files",
        "verify-storage",
        "recalculate-checksums",
        "find-orphan-files",
        "show-system-status",
    }:
        return _run_storage_command(args, settings)
    raise ValueError("Unknown command.")


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one maintenance command and return a shell-friendly exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        message = _run(args, get_settings())
    except (ApplicationError, OSError, ValueError, RuntimeError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    sys.stdout.write(f"{message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
