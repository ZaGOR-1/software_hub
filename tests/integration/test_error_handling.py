"""Integration coverage for middleware and centralized error rendering."""

import logging
import re
from pathlib import Path
from typing import Annotated

from app.core.config import AppSettings
from app.core.enums import AppEnvironment
from app.core.exceptions import EntityNotFound
from app.main import create_app
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.testclient import TestClient

APP_SECRET = "App-secret-2026-with-high-entropy-A9x7Q2mK"
CSRF_SECRET = "Csrf-secret-2026-with-high-entropy-B8v6P1nJ"


def add_test_routes(application: FastAPI) -> None:
    @application.get("/application-error")
    def application_error() -> None:
        raise EntityNotFound("Requested software does not exist.")

    @application.get("/unexpected-error")
    def unexpected_error() -> None:
        raise RuntimeError("private implementation detail")

    @application.get("/validate")
    def validate(value: Annotated[int, Query(gt=0)]) -> dict[str, int]:
        return {"value": value}

    @application.get("/teapot")
    def teapot() -> None:
        raise HTTPException(status_code=418, detail="Short and stout")

    @application.get("/inspect-proxy")
    def inspect_proxy(request: Request) -> dict[str, object]:
        return {
            "forwarded_for": request.headers.get("x-forwarded-for"),
            "trusted_proxy": request.state.trusted_proxy,
        }


def test_request_id_is_propagated_to_success_and_error_responses() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))
    add_test_routes(application)

    with TestClient(application) as client:
        success = client.get("/health", headers={"X-Request-ID": "client-request-42"})
        error = client.get("/application-error", headers={"X-Request-ID": "client-request-42"})

    assert success.headers["X-Request-ID"] == "client-request-42"
    assert error.headers["X-Request-ID"] == "client-request-42"
    assert error.json() == {
        "error": {
            "code": "not_found",
            "message": "Requested software does not exist.",
            "request_id": "client-request-42",
        }
    }


def test_invalid_request_id_is_replaced() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))

    with TestClient(application) as client:
        response = client.get("/health", headers={"X-Request-ID": "bad id with spaces"})

    generated = response.headers["X-Request-ID"]
    assert generated != "bad id with spaces"
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_framework_404_has_safe_json_envelope() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))

    with TestClient(application) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.headers["Cache-Control"] == "no-store"


def test_html_error_page_is_rendered_for_browser() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))

    with TestClient(application) as client:
        response = client.get(
            "/missing",
            headers={"Accept": "text/html", "X-Request-ID": "html-request"},
        )

    assert response.status_code == 404
    assert "404 — Not found" in response.text
    assert "html-request" in response.text
    assert "text/html" in response.headers["content-type"]


def test_validation_error_does_not_echo_invalid_input() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))
    add_test_routes(application)

    with TestClient(application) as client:
        response = client.get("/validate", params={"value": "super-secret-input"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "super-secret-input" not in response.text


def test_unknown_http_status_uses_generic_fallback_code() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))
    add_test_routes(application)

    with TestClient(application) as client:
        response = client.get("/teapot")

    assert response.status_code == 418
    assert response.json()["error"]["code"] == "bad_request"
    assert response.json()["error"]["message"] == "Short and stout"


def test_unexpected_production_error_never_exposes_traceback() -> None:
    settings = AppSettings(
        _env_file=None,
        app_environment=AppEnvironment.PRODUCTION,
        app_secret_key=APP_SECRET,
        csrf_secret=CSRF_SECRET,
        public_base_url="https://software.hotzagor.tech",
        trusted_hosts=("software.hotzagor.tech", "testserver"),
        docs_enabled=False,
    )
    application = create_app(settings)
    add_test_routes(application)

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/unexpected-error", headers={"host": "testserver"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private implementation detail" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Request-ID" in response.headers


def test_security_headers_are_applied_but_csp_skips_interactive_docs() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))

    with TestClient(application) as client:
        health = client.get("/health")
        docs = client.get("/docs")

    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert health.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in health.headers["Content-Security-Policy"]
    assert "Content-Security-Policy" not in docs.headers


def test_security_headers_can_be_disabled_for_controlled_testing() -> None:
    application = create_app(
        AppSettings(_env_file=None, app_environment="test", security_headers_enabled=False),
    )

    with TestClient(application) as client:
        response = client.get("/health")

    assert "X-Content-Type-Options" not in response.headers


def test_invalid_host_is_rejected_inside_correlated_middleware() -> None:
    application = create_app(
        AppSettings(_env_file=None, app_environment="test", trusted_hosts=("testserver",)),
    )

    with TestClient(application) as client:
        response = client.get("/health", headers={"host": "evil.example"})

    assert response.status_code == 400
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_untrusted_peer_cannot_inject_forwarding_headers() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))
    add_test_routes(application)

    with TestClient(application, client=("203.0.113.10", 50000)) as client:
        response = client.get("/inspect-proxy", headers={"X-Forwarded-For": "198.51.100.2"})

    assert response.json() == {"forwarded_for": None, "trusted_proxy": False}


def test_trusted_proxy_headers_reach_application() -> None:
    application = create_app(AppSettings(_env_file=None, app_environment="test"))
    add_test_routes(application)

    with TestClient(application, client=("127.0.0.1", 50000)) as client:
        response = client.get("/inspect-proxy", headers={"X-Forwarded-For": "198.51.100.2"})

    assert response.json() == {"forwarded_for": "198.51.100.2", "trusted_proxy": True}


def test_request_log_contains_bounded_metadata_only(tmp_path: Path) -> None:
    application = create_app(
        AppSettings(
            _env_file=None,
            app_environment="test",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'logging.db'}",
        )
    )
    request_logger = logging.getLogger("software_hub.request")
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = CaptureHandler()
    request_logger.addHandler(handler)
    try:
        with TestClient(application) as client:
            response = client.get(
                "/health",
                headers={"Authorization": "Bearer must-not-be-logged", "Cookie": "session=secret"},
            )
    finally:
        request_logger.removeHandler(handler)

    assert response.status_code == 200
    completed = next(record for record in records if record.getMessage() == "request_completed")
    assert completed.method == "GET"  # type: ignore[attr-defined]
    assert completed.route == "/health"  # type: ignore[attr-defined]
    assert completed.status_code == 200  # type: ignore[attr-defined]
    serialized = repr(completed.__dict__)
    assert "must-not-be-logged" not in serialized
    assert "session=secret" not in serialized
