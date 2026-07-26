"""Authenticated audit browser and pagination coverage for Phase 15."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.models.audit_log import AuditLog
from app.services.audit_service import AuditAction, AuditResult, append_audit_event
from app.services.auth_service import AuthService
from fastapi import FastAPI
from fastapi.testclient import TestClient

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def _login(application: FastAPI, client: TestClient) -> int:
    user = AuthService(application.state.database, application.state.settings).create_admin(
        username="audit-admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    match = _CSRF_PATTERN.search(page.text)
    assert match is not None
    response = client.post(
        "/admin/login",
        data={
            "username": "audit-admin",
            "password": "correct horse battery staple",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return user.id


def test_audit_route_requires_authentication(client: TestClient) -> None:
    response = client.get("/admin/audit", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_audit_filters_pagination_and_safe_rendering(
    application: FastAPI,
    client: TestClient,
) -> None:
    user_id = _login(application, client)
    base = datetime(2026, 7, 1, tzinfo=UTC)
    with application.state.database.transaction() as session:
        for index in range(120):
            row = append_audit_event(
                session,
                action=AuditAction.CATEGORY_UPDATED,
                result=AuditResult.SUCCESS,
                user_id=user_id,
                entity_type="category",
                entity_id=str(index + 1),
                request_id=f"req-{index:03d}",
                metadata={
                    "slug": f"category-{index}",
                    "password": "must-not-render",
                    "relative_storage_path": "/srv/software-hub/private",
                },
            )
            row.timestamp = base + timedelta(hours=index)
        failure = append_audit_event(
            session,
            action=AuditAction.ADMIN_LOGIN_FAILED,
            result=AuditResult.FAILURE,
            user_id=user_id,
            entity_type="user",
            entity_id=str(user_id),
            metadata={"reason": "invalid_credentials"},
        )
        failure.timestamp = datetime(2026, 7, 20, 12, tzinfo=UTC)

    first = client.get(
        "/admin/audit",
        params={"action": "category_updated", "page": 1},
    )
    assert first.status_code == 200
    assert "Знайдено: 120" in first.text
    assert first.text.count("category_updated") >= 50
    assert "must-not-render" not in first.text
    assert "/srv/software-hub/private" not in first.text
    assert "audit-admin" in first.text
    assert "Далі" in first.text

    third = client.get(
        "/admin/audit",
        params={"action": "category_updated", "page": 3},
    )
    assert third.status_code == 200
    assert "Сторінка 3 з 3" in third.text
    assert "req-000" in third.text
    assert "Назад" in third.text
    assert "Далі" not in third.text

    failed = client.get(
        "/admin/audit",
        params={
            "result": "failure",
            "date_from": "2026-07-20",
            "date_to": "2026-07-20",
        },
    )
    assert failed.status_code == 200
    assert "admin_login_failed" in failed.text
    assert "invalid_credentials" in failed.text
    assert "<td><code>category_updated</code></td>" not in failed.text


def test_audit_invalid_date_is_safe_form_error(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)

    response = client.get("/admin/audit", params={"date_from": "not-a-date"})

    assert response.status_code == 422
    assert "Дата початку має бути у форматі" in response.text
    assert "Traceback" not in response.text


def test_audit_repository_rows_remain_eager_after_session_close(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)

    response = client.get("/admin/audit")

    assert response.status_code == 200
    assert "audit-admin" in response.text
    with application.state.database.session() as session:
        rows = session.query(AuditLog).all()
        assert rows
