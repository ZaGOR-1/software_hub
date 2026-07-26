"""Audit metadata sanitization tests."""

from app.database.session import Database
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditAction, AuditResult, append_audit_event


def test_audit_hook_drops_sensitive_metadata(domain_database: Database) -> None:
    with domain_database.transaction() as session:
        row = append_audit_event(
            session,
            action=AuditAction.ADMIN_LOGIN_FAILED,
            result=AuditResult.FAILURE,
            metadata={
                "reason": "invalid_credentials",
                "password": "must-not-persist",
                "session_token": "must-not-persist",
            },
        )
        row_id = row.id

    with domain_database.session() as session:
        persisted = session.get(AuditLog, row_id)
        assert persisted is not None
        assert persisted.safe_metadata == {"reason": "invalid_credentials"}
