"""Administrator provisioning, login, lockout and password-change workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app.core.config import AppSettings
from app.core.exceptions import EntityConflict, EntityNotFound, ValidationError
from app.core.security import (
    PasswordService,
    hash_session_token,
    hmac_identifier,
    normalize_username,
)
from app.core.time import utc_now
from app.database.session import Database
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditAction, AuditResult, append_audit_event
from app.services.session_service import Clock, SessionCredentials, SessionService


@dataclass(frozen=True, slots=True)
class LoginContext:
    """Non-sensitive request metadata used for session and audit records."""

    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    previous_session_token: str | None = None


class AuthService:
    """Own atomic administrator authentication workflows."""

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
        self.passwords = PasswordService(settings)
        self.sessions = SessionService(database, settings, clock=clock)

    def _username_hash(self, username: str) -> str | None:
        secret = self.settings.app_secret_key
        if secret is None:
            return None
        return hmac_identifier(secret.get_secret_value(), "login-username", username)

    def create_admin(
        self,
        *,
        username: str,
        password: str,
        is_superuser: bool = True,
        request_id: str | None = "cli",
    ) -> User:
        """Create one manually provisioned administrator without a default password."""

        normalized = normalize_username(username)
        password_hash = self.passwords.hash_password(password, username=normalized)
        now = self.clock()
        try:
            with self.database.transaction() as session:
                repository = UserRepository(session)
                if repository.get_by_username(normalized) is not None:
                    raise EntityConflict("Administrator username already exists.")
                user = repository.add(
                    User(
                        username=normalized,
                        password_hash=password_hash,
                        is_active=True,
                        is_superuser=is_superuser,
                        password_changed_at=now,
                    )
                )
                append_audit_event(
                    session,
                    action=AuditAction.ADMIN_CREATED,
                    result=AuditResult.SUCCESS,
                    user_id=user.id,
                    entity_type="user",
                    entity_id=str(user.id),
                    request_id=request_id,
                )
                return user
        except IntegrityError as exc:
            raise EntityConflict("Administrator username already exists.") from exc

    def login(
        self,
        *,
        username: str,
        password: str,
        context: LoginContext | None = None,
    ) -> SessionCredentials | None:
        """Authenticate with generic failure semantics and create a rotated session."""

        context = context or LoginContext()
        try:
            normalized = normalize_username(username)
        except ValidationError:
            normalized = username.strip().casefold()
        now = self.clock()
        ip_hash, _ = self.sessions.client_hashes(
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        username_hash = self._username_hash(normalized)

        with self.database.transaction() as session:
            users = UserRepository(session)
            user = users.get_by_username(normalized)
            if user is None:
                self.passwords.verify_unknown_user(password)
                append_audit_event(
                    session,
                    action=AuditAction.ADMIN_LOGIN_FAILED,
                    result=AuditResult.FAILURE,
                    request_id=context.request_id,
                    ip_hash=ip_hash,
                    metadata={"reason": "invalid_credentials", "username_hash": username_hash},
                )
                return None

            if user.locked_until is not None and user.locked_until > now:
                self.passwords.verify_password(password, user.password_hash)
                append_audit_event(
                    session,
                    action=AuditAction.ADMIN_LOGIN_FAILED,
                    result=AuditResult.FAILURE,
                    user_id=user.id,
                    entity_type="user",
                    entity_id=str(user.id),
                    request_id=context.request_id,
                    ip_hash=ip_hash,
                    metadata={"reason": "temporarily_locked"},
                )
                return None

            if user.locked_until is not None and user.locked_until <= now:
                user.locked_until = None
                user.failed_login_attempts = 0

            valid_password = self.passwords.verify_password(password, user.password_hash)
            if not valid_password or not user.is_active:
                if valid_password:
                    reason = "inactive"
                else:
                    user.failed_login_attempts += 1
                    reason = "invalid_credentials"
                    if user.failed_login_attempts >= self.settings.login_max_failed_attempts:
                        user.locked_until = now + timedelta(
                            seconds=self.settings.login_lockout_seconds
                        )
                        reason = "lockout_started"
                append_audit_event(
                    session,
                    action=AuditAction.ADMIN_LOGIN_FAILED,
                    result=AuditResult.FAILURE,
                    user_id=user.id,
                    entity_type="user",
                    entity_id=str(user.id),
                    request_id=context.request_id,
                    ip_hash=ip_hash,
                    metadata={"reason": reason},
                )
                session.flush()
                return None

            if self.passwords.needs_rehash(user.password_hash):
                user.password_hash = self.passwords.hash_password(
                    password,
                    username=user.username,
                )
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = now

            if context.previous_session_token:
                previous_hash = hash_session_token(context.previous_session_token)
                previous = SessionRepository(session).get_by_token_hash(previous_hash)
                if previous is not None and previous.revoked_at is None:
                    previous.revoked_at = now

            credentials = self.sessions.create_record(
                session,
                user=user,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                now=now,
            )
            append_audit_event(
                session,
                action=AuditAction.ADMIN_LOGIN_SUCCESS,
                result=AuditResult.SUCCESS,
                user_id=user.id,
                entity_type="user",
                entity_id=str(user.id),
                request_id=context.request_id,
                ip_hash=ip_hash,
            )
            session.flush()
            return credentials

    def change_password(
        self,
        *,
        username: str,
        new_password: str,
        request_id: str | None = "cli",
    ) -> User:
        """Replace an administrator password and revoke every active session."""

        normalized = normalize_username(username)
        new_hash = self.passwords.hash_password(new_password, username=normalized)
        now = self.clock()
        with self.database.transaction() as session:
            user = UserRepository(session).get_by_username(normalized)
            if user is None:
                raise EntityNotFound("Administrator was not found.")
            user.password_hash = new_hash
            user.password_changed_at = now
            user.failed_login_attempts = 0
            user.locked_until = None
            revoked = SessionRepository(session).revoke_all_for_user(user.id, now=now)
            append_audit_event(
                session,
                action=AuditAction.ADMIN_PASSWORD_CHANGED,
                result=AuditResult.SUCCESS,
                user_id=user.id,
                entity_type="user",
                entity_id=str(user.id),
                request_id=request_id,
                metadata={"revoked_count": revoked},
            )
            session.flush()
            return user

    def get_user(self, username: str) -> User:
        """Resolve one normalized administrator for maintenance commands."""

        normalized = normalize_username(username)
        with self.database.session() as session:
            user = UserRepository(session).get_by_username(normalized)
            if user is None:
                raise EntityNotFound("Administrator was not found.")
            return user

    def revoke_sessions(
        self,
        *,
        username: str,
        request_id: str | None = "cli",
    ) -> int:
        """Revoke all active sessions for one administrator."""

        user = self.get_user(username)
        return self.sessions.revoke_all_for_user(user.id, request_id=request_id)
