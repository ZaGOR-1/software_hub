"""Append-only audit helpers and bounded administration queries."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import is_sensitive_key
from app.database.session import Database
from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository, AuditUserOption
from app.schemas.pagination import Page, Pagination

_ALLOWED_METADATA_KEYS = frozenset(
    {
        "backup_id",
        "changed",
        "checksum_verified",
        "cleared_count",
        "current",
        "deleted_count",
        "duplicate_count",
        "file_count",
        "total_bytes",
        "retention_deleted_count",
        "orphan_count",
        "mismatch_count",
        "verified_count",
        "dry_run",
        "file_extension",
        "file_size_bytes",
        "from",
        "initial_status",
        "physical_file_preserved",
        "reason",
        "release_id",
        "revoked_count",
        "scanner_status",
        "signature_assessment",
        "slug",
        "software_id",
        "storage_area",
        "to",
        "username_hash",
        "version",
    }
)
_MAX_METADATA_ITEMS = 24
_MAX_METADATA_STRING_LENGTH = 256
_MAX_METADATA_SEQUENCE_LENGTH = 20
_UNSUPPORTED = object()


class AuditAction(StrEnum):
    """Stable action identifiers emitted by application services."""

    ADMIN_CREATED = "admin_created"
    ADMIN_LOGIN_SUCCESS = "admin_login_success"
    ADMIN_LOGIN_FAILED = "admin_login_failed"
    ADMIN_LOGOUT = "admin_logout"
    ADMIN_PASSWORD_CHANGED = "admin_password_changed"  # nosec B105  # noqa: S105
    ADMIN_SESSIONS_REVOKED = "admin_sessions_revoked"
    EXPIRED_SESSIONS_CLEANED = "expired_sessions_cleaned"

    CATEGORY_CREATED = "category_created"
    CATEGORY_UPDATED = "category_updated"
    CATEGORY_DELETED = "category_deleted"
    TAG_CREATED = "tag_created"
    TAG_UPDATED = "tag_updated"
    TAG_DELETED = "tag_deleted"
    SOFTWARE_CREATED = "software_created"
    SOFTWARE_UPDATED = "software_updated"
    SOFTWARE_STATUS_CHANGED = "software_status_changed"
    SOFTWARE_VISIBILITY_CHANGED = "software_visibility_changed"
    RELEASE_CREATED = "release_created"
    RELEASE_UPDATED = "release_updated"
    RELEASE_STATUS_CHANGED = "release_status_changed"
    RELEASE_CURRENT_CHANGED = "release_current_changed"
    FILE_UPLOADED = "file_uploaded"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    FILE_REVIEWED = "file_reviewed"
    FILE_PUBLISHED = "file_published"
    FILE_DISABLED = "file_disabled"
    FILE_ARCHIVED = "file_archived"
    FILE_RESTORED = "file_restored"
    FILE_VERIFIED = "file_verified"
    FILE_CHECKSUM_RECALCULATED = "file_checksum_recalculated"
    FILE_METADATA_DELETED = "file_metadata_deleted"
    FILE_PERMANENTLY_DELETED = "file_permanently_deleted"

    BACKUP_CREATED = "backup_created"
    BACKUP_FAILED = "backup_failed"
    BACKUP_RESTORED = "backup_restored"


class AuditResult(StrEnum):
    """Normalized audit outcomes."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Request metadata safe to pass into transaction-oriented services."""

    user_id: int
    request_id: str | None = None
    ip_hash: str | None = None


@dataclass(frozen=True, slots=True)
class AuditFilters:
    """Typed filters for the authenticated audit browser."""

    action: str | None = None
    result: AuditResult | None = None
    user_id: int | None = None
    entity_type: str | None = None
    started_at: datetime | None = None
    ended_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuditFilterOptions:
    """Bounded option lists used by the audit filter form."""

    actions: tuple[str, ...]
    results: tuple[str, ...]
    entity_types: tuple[str, ...]
    users: tuple[AuditUserOption, ...]


@dataclass(frozen=True, slots=True)
class AuditPageSnapshot:
    """Audit records and filter options detached from the database session."""

    page: Page[AuditLog]
    options: AuditFilterOptions


def _safe_scalar(value: Any) -> str | int | float | bool | None | object:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _UNSUPPORTED
    if isinstance(value, StrEnum):
        return value.value[:_MAX_METADATA_STRING_LENGTH]
    if isinstance(value, str):
        return value[:_MAX_METADATA_STRING_LENGTH]
    return _UNSUPPORTED


def _safe_value(value: Any) -> str | int | float | bool | None | list[Any] | object:
    if isinstance(value, Mapping | bytes | bytearray):
        return _UNSUPPORTED
    if isinstance(value, Sequence) and not isinstance(value, str):
        values: list[Any] = []
        for item in value[:_MAX_METADATA_SEQUENCE_LENGTH]:
            cleaned = _safe_scalar(item)
            if cleaned is not _UNSUPPORTED:
                values.append(cleaned)
        return values
    return _safe_scalar(value)


def sanitize_audit_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only explicitly approved flat metadata keys and bounded JSON values."""

    cleaned: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        normalized = str(key).strip().casefold()
        if len(cleaned) >= _MAX_METADATA_ITEMS:
            break
        if normalized not in _ALLOWED_METADATA_KEYS or is_sensitive_key(normalized):
            continue
        cleaned_value = _safe_value(value)
        if cleaned_value is _UNSUPPORTED:
            continue
        cleaned[normalized] = cleaned_value
    return cleaned


def append_audit_event(  # noqa: PLR0913
    session: Session,
    *,
    action: AuditAction,
    result: AuditResult,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    request_id: str | None = None,
    ip_hash: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Append one sanitized audit row inside the caller-owned transaction."""

    return AuditRepository(session).add(
        AuditLog(
            user_id=user_id,
            action=action.value,
            result=result.value,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            ip_hash=ip_hash,
            safe_metadata=sanitize_audit_metadata(metadata),
        )
    )


def append_context_audit_event(
    session: Session,
    *,
    context: AuditContext | None,
    action: AuditAction,
    entity_type: str,
    entity_id: int | str,
    metadata: Mapping[str, Any] | None = None,
) -> AuditLog | None:
    """Append an event when an authenticated request context was supplied."""

    if context is None:
        return None
    return append_audit_event(
        session,
        action=action,
        result=AuditResult.SUCCESS,
        user_id=context.user_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        request_id=context.request_id,
        ip_hash=context.ip_hash,
        metadata=metadata,
    )


class AuditService:
    """Return bounded, eagerly loaded audit pages for authenticated operators."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_page(
        self,
        pagination: Pagination,
        filters: AuditFilters | None = None,
    ) -> AuditPageSnapshot:
        selected = filters or AuditFilters()
        with self.database.session() as session:
            repository = AuditRepository(session)
            page = repository.list_page(
                pagination,
                action=selected.action,
                result=selected.result.value if selected.result is not None else None,
                user_id=selected.user_id,
                entity_type=selected.entity_type,
                started_at=selected.started_at,
                ended_before=selected.ended_before,
            )
            options = AuditFilterOptions(
                actions=tuple(action.value for action in AuditAction),
                results=tuple(result.value for result in AuditResult),
                entity_types=repository.list_entity_types(limit=100),
                users=repository.list_user_options(limit=100),
            )
            return AuditPageSnapshot(page=page, options=options)
