"""Integration tests for server-side session validation and maintenance."""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import AppSettings
from app.database.session import Database
from app.models.audit_log import AuditLog
from app.models.session import UserSession
from app.services.auth_service import AuthService, LoginContext
from app.services.session_service import SessionCredentials, SessionService


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


def settings_for(
    test_settings: AppSettings,
    domain_database: Database,
    **updates: object,
) -> AppSettings:
    values: dict[str, object] = {"database_url": str(domain_database.engine.url)}
    values.update(updates)
    return test_settings.model_copy(update=values)


def create_login(
    test_settings: AppSettings,
    domain_database: Database,
    clock: MutableClock | None = None,
) -> tuple[AppSettings, SessionCredentials]:
    settings = settings_for(test_settings, domain_database)
    auth = AuthService(domain_database, settings, clock=clock or (lambda: datetime.now(UTC)))
    auth.create_admin(username="admin", password="correct horse battery staple")
    credentials = auth.login(username="admin", password="correct horse battery staple")
    assert credentials is not None
    return settings, credentials


def test_session_authentication_touches_idle_expiry(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    settings = settings_for(
        test_settings,
        domain_database,
        session_idle_timeout_seconds=120,
        session_absolute_timeout_seconds=600,
        session_touch_interval_seconds=30,
    )
    auth = AuthService(domain_database, settings, clock=clock)
    auth.create_admin(username="admin", password="correct horse battery staple")
    credentials = auth.login(username="admin", password="correct horse battery staple")
    assert credentials is not None

    service = SessionService(domain_database, settings, clock=clock)
    first = service.authenticate(credentials.token, ip_address="192.0.2.1", user_agent="pytest")
    assert first is not None
    initial_expiry = first.expires_at

    clock.advance(seconds=31)
    touched = service.authenticate(credentials.token)
    assert touched is not None
    assert touched.expires_at > initial_expiry
    assert touched.expires_at <= touched.absolute_expires_at


def test_idle_absolute_revoked_and_inactive_sessions_are_rejected(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    settings = settings_for(
        test_settings,
        domain_database,
        session_idle_timeout_seconds=60,
        session_absolute_timeout_seconds=120,
        session_touch_interval_seconds=10,
    )
    auth = AuthService(domain_database, settings, clock=clock)
    user = auth.create_admin(username="admin", password="correct horse battery staple")
    first = auth.login(username="admin", password="correct horse battery staple")
    assert first is not None
    service = SessionService(domain_database, settings, clock=clock)

    clock.advance(seconds=61)
    assert service.authenticate(first.token) is None

    second = auth.login(username="admin", password="correct horse battery staple")
    assert second is not None
    assert service.revoke(second.token, request_id="logout", ip_address="192.0.2.1") is True
    assert service.authenticate(second.token) is None
    assert service.revoke(second.token) is False
    assert service.revoke("unknown-token") is False
    assert service.revoke(None) is False

    third = auth.login(username="admin", password="correct horse battery staple")
    assert third is not None
    with domain_database.transaction() as session:
        persisted = session.get(type(user), user.id)
        assert persisted is not None
        persisted.is_active = False
    assert service.authenticate(third.token) is None


def test_absolute_expiry_caps_sliding_session(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    settings = settings_for(
        test_settings,
        domain_database,
        session_idle_timeout_seconds=90,
        session_absolute_timeout_seconds=120,
        session_touch_interval_seconds=1,
    )
    auth = AuthService(domain_database, settings, clock=clock)
    auth.create_admin(username="admin", password="correct horse battery staple")
    credentials = auth.login(username="admin", password="correct horse battery staple")
    assert credentials is not None
    service = SessionService(domain_database, settings, clock=clock)

    clock.advance(seconds=60)
    current = service.authenticate(credentials.token)
    assert current is not None
    assert current.expires_at == current.absolute_expires_at
    clock.advance(seconds=61)
    assert service.authenticate(credentials.token) is None


def test_cleanup_expired_and_revoke_all(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    settings = settings_for(
        test_settings,
        domain_database,
        session_idle_timeout_seconds=60,
        session_absolute_timeout_seconds=120,
        session_touch_interval_seconds=1,
    )
    auth = AuthService(domain_database, settings, clock=clock)
    user = auth.create_admin(username="admin", password="correct horse battery staple")
    one = auth.login(username="admin", password="correct horse battery staple")
    two = auth.login(username="admin", password="correct horse battery staple")
    assert one is not None
    assert two is not None
    service = SessionService(domain_database, settings, clock=clock)

    with domain_database.session() as session:
        sessions = session.query(UserSession).order_by(UserSession.id).all()
        preserved_id = sessions[0].id
    assert service.revoke_all_for_user(user.id, except_session_id=preserved_id) == 1

    clock.advance(seconds=121)
    assert service.cleanup_expired(request_id="cleanup") == 2
    with domain_database.session() as session:
        assert session.query(UserSession).count() == 0
        assert session.query(AuditLog).filter_by(action="expired_sessions_cleaned").count() == 1


def test_missing_session_secrets_fail_closed(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    settings = settings_for(test_settings, domain_database).model_copy(
        update={"app_secret_key": None, "csrf_secret": None}
    )
    service = SessionService(domain_database, settings)

    with pytest.raises(RuntimeError, match="requires"):
        service.client_hashes(ip_address="127.0.0.1", user_agent="pytest")
    assert service.authenticate(None) is None


def test_client_fingerprint_changes_are_audit_signals_only(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    settings = settings_for(test_settings, domain_database)
    auth = AuthService(domain_database, settings)
    auth.create_admin(username="admin", password="correct horse battery staple")
    credentials = auth.login(
        username="admin",
        password="correct horse battery staple",
        context=LoginContext(ip_address="192.0.2.10", user_agent="browser-a"),
    )
    assert credentials is not None

    service = SessionService(domain_database, settings)
    unchanged = service.authenticate(
        credentials.token,
        ip_address="192.0.2.10",
        user_agent="browser-a",
    )
    assert unchanged is not None
    assert unchanged.ip_changed is False
    assert unchanged.user_agent_changed is False

    changed = service.authenticate(
        credentials.token,
        ip_address="198.51.100.25",
        user_agent="browser-b",
    )
    assert changed is not None
    assert changed.ip_changed is True
    assert changed.user_agent_changed is True
