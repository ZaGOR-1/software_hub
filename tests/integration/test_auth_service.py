"""Integration tests for administrator provisioning, login and lockout."""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import AppSettings
from app.core.exceptions import EntityConflict, EntityNotFound, ValidationError
from app.core.security import hash_session_token
from app.database.session import Database
from app.models.audit_log import AuditLog
from app.models.session import UserSession
from app.models.user import User
from app.services.auth_service import AuthService, LoginContext


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


def auth_settings(test_settings: AppSettings, domain_database: Database) -> AppSettings:
    return test_settings.model_copy(update={"database_url": str(domain_database.engine.url)})


def test_create_admin_hashes_password_and_audits(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    service = AuthService(domain_database, auth_settings(test_settings, domain_database))
    user = service.create_admin(username=" Admin.User ", password="correct horse battery staple")

    assert user.username == "admin.user"
    assert user.password_hash.startswith("$argon2id$")
    assert "correct horse" not in user.password_hash
    assert user.password_changed_at is not None

    with domain_database.session() as session:
        assert session.query(User).count() == 1
        audit = session.query(AuditLog).one()
        assert audit.action == "admin_created"
        assert audit.user_id == user.id


def test_create_admin_rejects_duplicate_and_bad_password(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    service = AuthService(domain_database, auth_settings(test_settings, domain_database))
    service.create_admin(username="admin", password="correct horse battery staple")

    with pytest.raises(EntityConflict):
        service.create_admin(username="ADMIN", password="another strong password")
    with pytest.raises(ValidationError):
        service.create_admin(username="other", password="short")


def test_unknown_and_wrong_user_fail_generically_and_audit(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    service = AuthService(domain_database, auth_settings(test_settings, domain_database))
    service.create_admin(username="admin", password="correct horse battery staple")

    assert service.login(username="missing", password="wrong password") is None
    assert service.login(username="admin", password="wrong password") is None

    with domain_database.session() as session:
        failures = session.query(AuditLog).filter_by(action="admin_login_failed").all()
        assert len(failures) == 2
        assert {row.safe_metadata["reason"] for row in failures} == {"invalid_credentials"}
        assert all("password" not in row.safe_metadata for row in failures)


def test_lockout_and_expiry(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    settings = auth_settings(test_settings, domain_database).model_copy(
        update={"login_max_failed_attempts": 3, "login_lockout_seconds": 120}
    )
    service = AuthService(domain_database, settings, clock=clock)
    service.create_admin(username="admin", password="correct horse battery staple")

    for _ in range(3):
        assert service.login(username="admin", password="wrong password") is None
    assert service.login(username="admin", password="correct horse battery staple") is None

    with domain_database.session() as session:
        user = session.query(User).filter_by(username="admin").one()
        assert user.failed_login_attempts == 3
        assert user.locked_until == clock.value + timedelta(seconds=120)

    clock.advance(seconds=121)
    credentials = service.login(username="admin", password="correct horse battery staple")
    assert credentials is not None

    with domain_database.session() as session:
        user = session.query(User).filter_by(username="admin").one()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


def test_successful_login_creates_hashed_session_and_rotates(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    settings = auth_settings(test_settings, domain_database)
    service = AuthService(domain_database, settings)
    service.create_admin(username="admin", password="correct horse battery staple")
    first = service.login(
        username="admin",
        password="correct horse battery staple",
        context=LoginContext(ip_address="192.0.2.10", user_agent="pytest", request_id="r1"),
    )
    assert first is not None

    second = service.login(
        username="admin",
        password="correct horse battery staple",
        context=LoginContext(
            ip_address="192.0.2.10",
            user_agent="pytest",
            request_id="r2",
            previous_session_token=first.token,
        ),
    )
    assert second is not None
    assert second.token != first.token

    with domain_database.session() as session:
        old = (
            session.query(UserSession)
            .filter_by(session_token_hash=hash_session_token(first.token))
            .one()
        )
        new = (
            session.query(UserSession)
            .filter_by(session_token_hash=hash_session_token(second.token))
            .one()
        )
        user = session.query(User).filter_by(username="admin").one()
        assert old.revoked_at is not None
        assert new.revoked_at is None
        assert len(new.session_token_hash) == 64
        assert new.ip_hash is not None
        assert new.user_agent_hash is not None
        assert new.csrf_secret_hash is not None
        assert user.last_login_at is not None
        assert session.query(AuditLog).filter_by(action="admin_login_success").count() == 2


def test_inactive_user_and_malformed_username_fail(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    service = AuthService(domain_database, auth_settings(test_settings, domain_database))
    user = service.create_admin(username="admin", password="correct horse battery staple")
    with domain_database.transaction() as session:
        persisted = session.get(User, user.id)
        assert persisted is not None
        persisted.is_active = False

    assert service.login(username="admin", password="correct horse battery staple") is None
    assert service.login(username="<invalid>", password="anything at all") is None


def test_password_change_revokes_sessions_and_new_password_works(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    service = AuthService(domain_database, auth_settings(test_settings, domain_database))
    service.create_admin(username="admin", password="correct horse battery staple")
    credentials = service.login(username="admin", password="correct horse battery staple")
    assert credentials is not None

    changed = service.change_password(username="admin", new_password="new strong password value")
    assert changed.password_changed_at is not None
    assert service.login(username="admin", password="correct horse battery staple") is None
    assert service.login(username="admin", password="new strong password value") is not None

    with domain_database.session() as session:
        old = (
            session.query(UserSession)
            .filter_by(session_token_hash=hash_session_token(credentials.token))
            .one()
        )
        assert old.revoked_at is not None
        audit = session.query(AuditLog).filter_by(action="admin_password_changed").one()
        assert audit.safe_metadata["revoked_count"] == 1


def test_get_user_and_revoke_sessions(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    service = AuthService(domain_database, auth_settings(test_settings, domain_database))
    user = service.create_admin(username="admin", password="correct horse battery staple")
    assert service.login(username="admin", password="correct horse battery staple") is not None
    assert service.get_user("ADMIN").id == user.id
    assert service.revoke_sessions(username="admin") == 1

    with pytest.raises(EntityNotFound):
        service.get_user("missing")
