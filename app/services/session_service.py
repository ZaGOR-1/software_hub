"""Server-side administrator session creation, validation and revocation."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import AppSettings
from app.core.security import (
    derive_csrf_secret_hash,
    generate_session_token,
    hash_session_token,
    hmac_identifier,
)
from app.core.time import utc_now
from app.database.session import Database
from app.models.session import UserSession
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.services.audit_service import AuditAction, AuditResult, append_audit_event

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class SessionCredentials:
    """Raw cookie token returned exactly once when a session is created."""

    token: str
    user: User
    expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """Validated server-side session context for protected routes."""

    session_id: int
    user: User
    expires_at: datetime
    absolute_expires_at: datetime
    ip_changed: bool
    user_agent_changed: bool
    csrf_secret_hash: str = field(repr=False)


class SessionService:
    """Coordinate session persistence with sliding idle expiry."""

    def __init__(
        self,
        database: Database,
        settings: AppSettings,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self.database = database
        self.settings = settings
        self.clock = clock

    def _require_secrets(self) -> tuple[str, str]:
        app_secret = self.settings.app_secret_key
        csrf_secret = self.settings.csrf_secret
        if app_secret is None or csrf_secret is None:
            raise RuntimeError("Session authentication requires app_secret_key and csrf_secret.")
        return app_secret.get_secret_value(), csrf_secret.get_secret_value()

    def client_hashes(
        self,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[str | None, str | None]:
        """Hash client metadata for limited audit use without persisting raw values."""

        app_secret, _ = self._require_secrets()
        return (
            hmac_identifier(app_secret, "client-ip", ip_address),
            hmac_identifier(app_secret, "user-agent", user_agent),
        )

    def create_record(
        self,
        session: Session,
        *,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
        now: datetime,
    ) -> SessionCredentials:
        """Create a session inside an existing caller-owned transaction."""

        _, csrf_secret = self._require_secrets()
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        ip_hash, user_agent_hash = self.client_hashes(
            ip_address=ip_address,
            user_agent=user_agent,
        )
        absolute_expires_at = now + timedelta(
            seconds=self.settings.session_absolute_timeout_seconds
        )
        expires_at = min(
            now + timedelta(seconds=self.settings.session_idle_timeout_seconds),
            absolute_expires_at,
        )
        record = SessionRepository(session).add(
            UserSession(
                session_token_hash=token_hash,
                user=user,
                created_at=now,
                last_activity_at=now,
                expires_at=expires_at,
                absolute_expires_at=absolute_expires_at,
                user_agent_hash=user_agent_hash,
                ip_hash=ip_hash,
                csrf_secret_hash=derive_csrf_secret_hash(csrf_secret, token_hash),
            )
        )
        return SessionCredentials(
            token=raw_token,
            user=user,
            expires_at=record.expires_at,
            absolute_expires_at=record.absolute_expires_at,
        )

    def authenticate(
        self,
        raw_token: str | None,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthenticatedSession | None:
        """Validate a session and periodically advance its bounded idle deadline."""

        if raw_token is None or not raw_token:
            return None
        token_hash = hash_session_token(raw_token)
        now = self.clock()
        with self.database.transaction() as session:
            record = SessionRepository(session).get_by_token_hash(token_hash)
            if record is None or record.revoked_at is not None:
                return None
            if record.expires_at <= now or record.absolute_expires_at <= now:
                return None
            if not record.user.is_active:
                return None

            touch_after = timedelta(seconds=self.settings.session_touch_interval_seconds)
            if now - record.last_activity_at >= touch_after:
                record.last_activity_at = now
                record.expires_at = min(
                    now + timedelta(seconds=self.settings.session_idle_timeout_seconds),
                    record.absolute_expires_at,
                )
                session.flush()

            # Fingerprints are audit signals only; a changed network or browser does not
            # invalidate an otherwise valid session.
            current_ip_hash, current_user_agent_hash = self.client_hashes(
                ip_address=ip_address,
                user_agent=user_agent,
            )
            ip_changed = (
                record.ip_hash is not None
                and current_ip_hash is not None
                and not hmac.compare_digest(record.ip_hash, current_ip_hash)
            )
            user_agent_changed = (
                record.user_agent_hash is not None
                and current_user_agent_hash is not None
                and not hmac.compare_digest(record.user_agent_hash, current_user_agent_hash)
            )
            return AuthenticatedSession(
                session_id=record.id,
                user=record.user,
                expires_at=record.expires_at,
                absolute_expires_at=record.absolute_expires_at,
                ip_changed=ip_changed,
                user_agent_changed=user_agent_changed,
                csrf_secret_hash=record.csrf_secret_hash,
            )

    def revoke(
        self,
        raw_token: str | None,
        *,
        request_id: str | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Revoke one session bearer token and append a logout audit row."""

        if raw_token is None or not raw_token:
            return False
        now = self.clock()
        token_hash = hash_session_token(raw_token)
        ip_hash, _ = self.client_hashes(ip_address=ip_address, user_agent=None)
        with self.database.transaction() as session:
            record = SessionRepository(session).get_by_token_hash(token_hash)
            if record is None or record.revoked_at is not None:
                return False
            record.revoked_at = now
            append_audit_event(
                session,
                action=AuditAction.ADMIN_LOGOUT,
                result=AuditResult.SUCCESS,
                user_id=record.user_id,
                entity_type="session",
                entity_id=str(record.id),
                request_id=request_id,
                ip_hash=ip_hash,
            )
            session.flush()
            return True

    def revoke_all_for_user(
        self,
        user_id: int,
        *,
        except_session_id: int | None = None,
        request_id: str | None = None,
    ) -> int:
        """Revoke active sessions for one administrator."""

        now = self.clock()
        with self.database.transaction() as session:
            count = SessionRepository(session).revoke_all_for_user(
                user_id,
                now=now,
                except_session_id=except_session_id,
            )
            append_audit_event(
                session,
                action=AuditAction.ADMIN_SESSIONS_REVOKED,
                result=AuditResult.SUCCESS,
                user_id=user_id,
                entity_type="user",
                entity_id=str(user_id),
                request_id=request_id,
                metadata={"revoked_count": count},
            )
            return count

    def cleanup_expired(self, *, request_id: str | None = None) -> int:
        """Delete sessions whose idle or absolute lifetime has elapsed."""

        now = self.clock()
        with self.database.transaction() as session:
            count = SessionRepository(session).delete_expired(now)
            append_audit_event(
                session,
                action=AuditAction.EXPIRED_SESSIONS_CLEANED,
                result=AuditResult.SUCCESS,
                request_id=request_id,
                metadata={"deleted_count": count},
            )
            return count
