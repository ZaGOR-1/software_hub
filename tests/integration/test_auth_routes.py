"""HTTP tests for CSRF-protected login, admin access and logout."""

import re
from pathlib import Path

from app.core.config import AppSettings
from app.core.constants import MAXIMUM_FORM_FIELDS
from app.core.csrf import CSRFTokenService
from app.core.security import hash_session_token
from app.database.migrations_helpers import upgrade_database
from app.main import create_app
from app.models.session import UserSession
from app.models.user import User
from app.services.auth_service import AuthService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def create_admin(application: FastAPI, password: str = "correct horse battery staple") -> User:
    settings: AppSettings = application.state.settings
    return AuthService(application.state.database, settings).create_admin(
        username="admin",
        password=password,
    )


def extract_csrf(html: str) -> str:
    match = _CSRF_PATTERN.search(html)
    assert match is not None
    return match.group(1)


def tamper_csrf(token: str) -> str:
    version, issued_at, nonce, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    return f"{version}.{issued_at}.{nonce}.{replacement}{signature[1:]}"


def login(
    client: TestClient,
    *,
    username: str = "admin",
    password: str = "correct horse battery staple",
    follow_redirects: bool = False,
    headers: dict[str, str] | None = None,
) -> Response:
    page = client.get("/admin/login")
    token = extract_csrf(page.text)
    return client.post(
        "/admin/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=follow_redirects,
        headers=headers,
    )


def logout_token(client: TestClient) -> str:
    dashboard = client.get("/admin")
    assert dashboard.status_code == 200
    return extract_csrf(dashboard.text)


def test_login_page_and_protected_redirect(client: TestClient) -> None:
    page = client.get("/admin/login")
    assert page.status_code == 200
    assert "Вхід до адміністрування" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert extract_csrf(page.text)

    cookie = page.headers["set-cookie"]
    assert "software_hub_login_csrf=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/admin/login" in cookie
    assert "Secure" not in cookie

    protected = client.get("/admin", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/admin/login"


def test_unknown_and_wrong_password_have_identical_feedback(
    application: FastAPI,
    client: TestClient,
) -> None:
    create_admin(application)
    unknown = login(client, username="missing", password="wrong password")
    wrong = login(client, username="admin", password="wrong password")

    assert unknown.status_code == wrong.status_code == 401
    assert "Невірний логін або пароль." in unknown.text
    assert "Невірний логін або пароль." in wrong.text
    assert "missing" not in unknown.text or 'value="missing"' in unknown.text
    assert extract_csrf(unknown.text) != extract_csrf(wrong.text)


def test_login_cookie_dashboard_and_logout(application: FastAPI, client: TestClient) -> None:
    create_admin(application)
    login_response = login(client)
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/admin"
    cookie = login_response.headers["set-cookie"]
    assert "software_hub_session=" in cookie
    assert "software_hub_login_csrf=" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    session_cookies = [
        value
        for value in login_response.headers.get_list("set-cookie")
        if value.startswith("software_hub_session=")
    ]
    assert len(session_cookies) == 1
    assert "Path=/;" in session_cookies[0]
    assert "Secure" not in session_cookies[0]

    dashboard = client.get("/admin")
    assert dashboard.status_code == 200
    assert "admin" in dashboard.text
    assert dashboard.headers["cache-control"] == "no-store"
    csrf_token = extract_csrf(dashboard.text)

    raw_token = client.cookies.get("software_hub_session")
    assert raw_token is not None
    logout_response = client.post(
        "/admin/logout",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/admin/login"

    with application.state.database.session() as session:
        record = (
            session.query(UserSession)
            .filter_by(session_token_hash=hash_session_token(raw_token))
            .one()
        )
        assert record.revoked_at is not None

    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_login_rotates_existing_cookie(application: FastAPI, client: TestClient) -> None:
    create_admin(application)
    first_response = login(client)
    first_token = client.cookies.get("software_hub_session")
    assert first_response.status_code == 303
    assert first_token is not None
    first_csrf_token = logout_token(client)

    settings: AppSettings = application.state.settings
    login_csrf = CSRFTokenService(settings).issue_login_context()
    client.cookies.set(settings.login_csrf_cookie_name, login_csrf.cookie_value)
    second_response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct horse battery staple",
            "csrf_token": login_csrf.token,
        },
        follow_redirects=False,
    )
    second_token = client.cookies.get("software_hub_session")
    assert second_response.status_code == 303
    assert second_token is not None
    assert second_token != first_token

    old_csrf = client.post(
        "/admin/logout",
        data={"csrf_token": first_csrf_token},
        headers={"accept": "application/json"},
        follow_redirects=False,
    )
    assert old_csrf.status_code == 403

    with application.state.database.session() as session:
        old = (
            session.query(UserSession)
            .filter_by(session_token_hash=hash_session_token(first_token))
            .one()
        )
        assert old.revoked_at is not None


def test_already_authenticated_login_page_redirects(
    application: FastAPI,
    client: TestClient,
) -> None:
    create_admin(application)
    login(client)
    response = client.get("/admin/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def test_login_validation_does_not_echo_password(application: FastAPI, client: TestClient) -> None:
    create_admin(application)
    secret = "x" * 4097
    response = login(
        client,
        password=secret,
        headers={"accept": "application/json"},
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_login_rejects_missing_invalid_and_cross_browser_csrf(
    application: FastAPI,
    client: TestClient,
) -> None:
    create_admin(application)

    missing = client.post(
        "/admin/login",
        data={"username": "admin", "password": "correct horse battery staple"},
        headers={"accept": "application/json"},
    )
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_error"

    page = client.get("/admin/login")
    token = extract_csrf(page.text)
    invalid = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct horse battery staple",
            "csrf_token": tamper_csrf(token),
        },
        headers={"accept": "application/json"},
    )
    assert invalid.status_code == 403

    with TestClient(application) as other_client:
        other_client.get("/admin/login")
        crossed = other_client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "correct horse battery staple",
                "csrf_token": token,
            },
            headers={"accept": "application/json"},
        )
    assert crossed.status_code == 403

    with application.state.database.session() as session:
        user = session.query(User).filter_by(username="admin").one()
        assert user.failed_login_attempts == 0


def test_login_rejects_urlencoded_field_flood_before_authentication(
    application: FastAPI,
    client: TestClient,
) -> None:
    create_admin(application)
    page = client.get("/admin/login")
    token = extract_csrf(page.text)
    data = {
        "username": "admin",
        "password": "correct horse battery staple",
        "csrf_token": token,
        **{f"padding_{index}": "x" for index in range(MAXIMUM_FORM_FIELDS)},
    }

    response = client.post(
        "/admin/login",
        data=data,
        headers={"accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"

    with application.state.database.session() as session:
        user = session.query(User).filter_by(username="admin").one()
        assert user.failed_login_attempts == 0


def test_logout_requires_valid_session_bound_csrf(
    application: FastAPI,
    client: TestClient,
) -> None:
    create_admin(application)
    login(client)
    valid_token = logout_token(client)
    raw_session = client.cookies.get("software_hub_session")
    assert raw_session is not None

    missing = client.post(
        "/admin/logout",
        data={},
        headers={"accept": "application/json"},
        follow_redirects=False,
    )
    assert missing.status_code == 403

    oversized_form = client.post(
        "/admin/logout",
        data={"csrf_token": "x" * 513},
        headers={"accept": "application/json"},
        follow_redirects=False,
    )
    assert oversized_form.status_code == 403

    oversized_header = client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": "x" * 513, "accept": "application/json"},
        follow_redirects=False,
    )
    assert oversized_header.status_code == 403

    invalid = client.post(
        "/admin/logout",
        data={"csrf_token": tamper_csrf(valid_token)},
        headers={"accept": "application/json"},
        follow_redirects=False,
    )
    assert invalid.status_code == 403
    assert client.get("/admin").status_code == 200

    with application.state.database.session() as session:
        record = (
            session.query(UserSession)
            .filter_by(session_token_hash=hash_session_token(raw_session))
            .one()
        )
        assert record.revoked_at is None


def test_session_csrf_cannot_be_reused_by_another_session(application: FastAPI) -> None:
    create_admin(application)
    with TestClient(application) as first, TestClient(application) as second:
        assert login(first).status_code == 303
        assert login(second).status_code == 303
        first_token = logout_token(first)

        crossed = second.post(
            "/admin/logout",
            data={"csrf_token": first_token},
            headers={"accept": "application/json"},
            follow_redirects=False,
        )
        assert crossed.status_code == 403
        assert second.get("/admin").status_code == 200


def test_production_login_and_session_cookies_are_secure(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'production.db'}"
    settings = AppSettings(
        app_environment="production",
        app_secret_key="prod-app-secret-0123456789-ABCDEFGH",
        csrf_secret="prod-csrf-secret-9876543210-HGFEDCBA",
        public_base_url="https://software.hotzagor.tech",
        trusted_hosts=("software.hotzagor.tech",),
        database_url=database_url,
        storage_root=tmp_path / "storage",
        temporary_root=tmp_path / "storage" / "temporary",
        quarantine_root=tmp_path / "storage" / "quarantine",
        icons_root=tmp_path / "storage" / "icons",
        backup_root=tmp_path / "backups",
    )
    upgrade_database(database_url)
    application = create_app(settings)

    with TestClient(
        application,
        base_url="https://software.hotzagor.tech",
    ) as production_client:
        create_admin(application)
        page = production_client.get("/admin/login")
        assert "Secure" in page.headers["set-cookie"]
        token = extract_csrf(page.text)
        response = production_client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "correct horse battery staple",
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "Secure" in response.headers["set-cookie"]


def test_authenticated_csrf_header_avoids_form_parsing(
    application: FastAPI,
    client: TestClient,
) -> None:
    create_admin(application)
    assert login(client).status_code == 303
    token = logout_token(client)

    response = client.post(
        "/admin/logout",
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
