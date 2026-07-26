"""FastAPI dependencies for administrator sessions and CSRF-protected forms."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import AppSettings
from app.core.constants import (
    MAXIMUM_FORM_FIELD_SIZE,
    MAXIMUM_FORM_FIELDS,
    MAXIMUM_FORM_FILES,
    UPLOAD_REQUEST_OVERHEAD_BYTES,
)
from app.core.csrf import CSRFTokenService
from app.core.exceptions import CSRFError, PayloadTooLarge, ValidationError
from app.database.session import DatabaseDependency
from app.services.session_service import AuthenticatedSession, SessionService


def client_ip(request: Request) -> str | None:
    """Return the post-proxy-policy peer address used only for keyed hashing."""

    return request.client.host if request.client is not None else None


def optional_admin_session(
    request: Request,
    database: DatabaseDependency,
) -> AuthenticatedSession | None:
    """Resolve and validate the opaque session cookie when present."""

    settings: AppSettings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    return SessionService(database, settings).authenticate(
        token,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


OptionalAdminSession = Annotated[
    AuthenticatedSession | None,
    Depends(optional_admin_session),
]


def require_admin_session(
    request: Request,
    session: OptionalAdminSession,
) -> AuthenticatedSession:
    """Protect admin routes and redirect unauthenticated browser requests to login."""

    if session is None:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    request.state.admin_session = session
    request.state.admin_user = session.user
    return session


RequiredAdminSession = Annotated[
    AuthenticatedSession,
    Depends(require_admin_session),
]


async def _csrf_request_value(request: Request, settings: AppSettings) -> str | None:
    """Read a bounded header token first, otherwise the hidden form field."""

    header_value = request.headers.get(settings.csrf_header_name)
    if header_value is not None:
        if len(header_value) > settings.csrf_token_max_length:
            raise CSRFError(safe_metadata={"reason": "oversized"})
        return header_value

    form = await request.form(
        max_files=MAXIMUM_FORM_FILES,
        max_fields=MAXIMUM_FORM_FIELDS,
        max_part_size=MAXIMUM_FORM_FIELD_SIZE,
    )
    value = form.get(settings.csrf_form_field_name)
    if not isinstance(value, str):
        return None
    if len(value) > settings.csrf_token_max_length:
        raise CSRFError(safe_metadata={"reason": "oversized"})
    return value


async def require_login_csrf(request: Request) -> None:
    """Verify the short-lived pre-authentication token used by the login form."""

    settings: AppSettings = request.app.state.settings
    token = await _csrf_request_value(request, settings)
    CSRFTokenService(settings).verify_login_token(
        cookie_value=request.cookies.get(settings.login_csrf_cookie_name),
        token=token,
    )


LoginCSRFProtection = Annotated[None, Depends(require_login_csrf)]


async def require_session_csrf(
    request: Request,
    session: RequiredAdminSession,
) -> AuthenticatedSession:
    """Require an authenticated session and a matching session-bound form token."""

    settings: AppSettings = request.app.state.settings
    token = await _csrf_request_value(request, settings)
    CSRFTokenService(settings).verify_session_token(
        csrf_secret_hash=session.csrf_secret_hash,
        token=token,
    )
    return session


CSRFProtectedAdminSession = Annotated[
    AuthenticatedSession,
    Depends(require_session_csrf),
]


def _validate_upload_content_length(request: Request, settings: AppSettings) -> None:
    raw_value = request.headers.get("content-length")
    if raw_value is None:
        return
    try:
        content_length = int(raw_value)
    except ValueError as exc:
        raise ValidationError("Content-Length is invalid.") from exc
    if content_length < 0:
        raise ValidationError("Content-Length is invalid.")
    if content_length > settings.max_upload_size + UPLOAD_REQUEST_OVERHEAD_BYTES:
        raise PayloadTooLarge()


async def require_upload_session_csrf(
    request: Request,
    session: RequiredAdminSession,
) -> AuthenticatedSession:
    """Reject oversized multipart requests before parsing CSRF form data."""

    settings: AppSettings = request.app.state.settings
    _validate_upload_content_length(request, settings)
    token = await _csrf_request_value(request, settings)
    CSRFTokenService(settings).verify_session_token(
        csrf_secret_hash=session.csrf_secret_hash,
        token=token,
    )
    return session


UploadCSRFProtectedAdminSession = Annotated[
    AuthenticatedSession,
    Depends(require_upload_session_csrf),
]
