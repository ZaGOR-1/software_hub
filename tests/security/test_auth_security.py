"""Security acceptance tests for Phase 6 authentication controls."""

from app.core.config import AppSettings
from app.core.logging import JsonFormatter
from app.database.session import Database
from app.models.audit_log import AuditLog
from app.services.auth_service import AuthService, LoginContext


def test_audit_and_logs_never_store_password_or_raw_client_values(
    test_settings: AppSettings,
    domain_database: Database,
) -> None:
    settings = test_settings.model_copy(update={"database_url": str(domain_database.engine.url)})
    service = AuthService(domain_database, settings)
    service.create_admin(username="admin", password="correct horse battery staple")
    supplied_password = "this password must never be logged"
    service.login(
        username="admin",
        password=supplied_password,
        context=LoginContext(
            ip_address="203.0.113.45",
            user_agent="Sensitive Browser Value",
            request_id="security-test",
        ),
    )

    with domain_database.session() as session:
        rows = session.query(AuditLog).all()
        serialized = repr([(row.action, row.safe_metadata, row.ip_hash) for row in rows])
        assert supplied_password not in serialized
        assert "203.0.113.45" not in serialized
        assert "Sensitive Browser Value" not in serialized


def test_json_formatter_redacts_authentication_fields() -> None:
    import logging

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authentication_event",
        args=(),
        exc_info=None,
    )
    record.password = "secret-password"
    record.session_token = "raw-token"
    record.csrf_token = "raw-csrf-token"
    record.safe_reason = "invalid_credentials"
    output = JsonFormatter().format(record)

    assert "secret-password" not in output
    assert "raw-token" not in output
    assert "raw-csrf-token" not in output
    assert "[REDACTED]" in output
    assert "invalid_credentials" in output
