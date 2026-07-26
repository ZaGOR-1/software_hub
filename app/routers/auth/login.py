"""Server-rendered administrator login and logout routes."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from starlette.templating import Jinja2Templates

from app.core.config import AppSettings
from app.core.constants import (
    MAXIMUM_FORM_FIELD_SIZE,
    MAXIMUM_FORM_FIELDS,
    MAXIMUM_FORM_FILES,
)
from app.core.csrf import CSRFTokenService
from app.database.session import DatabaseDependency
from app.routers.auth.dependencies import (
    CSRFProtectedAdminSession,
    LoginCSRFProtection,
    OptionalAdminSession,
    client_ip,
)
from app.services.auth_service import AuthService, LoginContext
from app.services.session_service import SessionService

router = APIRouter(prefix="/admin", tags=["authentication"])
_TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")
_GENERIC_LOGIN_ERROR = "Невірний логін або пароль."


class _LoginCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=4096)


async def _login_credentials(request: Request) -> _LoginCredentials:
    form = await request.form(
        max_files=MAXIMUM_FORM_FILES,
        max_fields=MAXIMUM_FORM_FIELDS,
        max_part_size=MAXIMUM_FORM_FIELD_SIZE,
    )
    try:
        return _LoginCredentials.model_validate(
            {
                "username": form.get("username"),
                "password": form.get("password"),
            }
        )
    except PydanticValidationError as exc:
        raise RequestValidationError(exc.errors(include_input=False)) from exc


def _set_login_csrf_cookie(response: Response, settings: AppSettings, value: str) -> None:
    response.set_cookie(
        key=settings.login_csrf_cookie_name,
        value=value,
        max_age=settings.login_csrf_ttl_seconds,
        path=settings.login_csrf_cookie_path,
        secure=settings.effective_session_cookie_secure,
        httponly=True,
        samesite=settings.login_csrf_cookie_same_site,
    )


def _delete_login_csrf_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(
        key=settings.login_csrf_cookie_name,
        path=settings.login_csrf_cookie_path,
        secure=settings.effective_session_cookie_secure,
        httponly=True,
        samesite=settings.login_csrf_cookie_same_site,
    )


def _render_login(
    request: Request,
    *,
    status_code: int = 200,
    error: str | None = None,
    username: str = "",
) -> Response:
    settings: AppSettings = request.app.state.settings
    csrf_context = CSRFTokenService(settings).issue_login_context()
    response = _TEMPLATES.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "app_name": settings.app_name,
            "error": error,
            "username": username,
            "csrf_token": csrf_context.token,
            "csrf_field_name": settings.csrf_form_field_name,
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    _set_login_csrf_cookie(response, settings, csrf_context.cookie_value)
    return response


def _set_session_cookie(
    response: RedirectResponse,
    settings: AppSettings,
    token: str,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_absolute_timeout_seconds,
        path=settings.session_cookie_path,
        secure=settings.effective_session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_same_site,
    )


@router.get("/login", include_in_schema=False)
def login_page(
    request: Request,
    current_session: OptionalAdminSession,
) -> Response:
    """Render the login form or redirect an already authenticated administrator."""

    if current_session is not None:
        return RedirectResponse(url="/admin", status_code=303)
    return _render_login(request)


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    database: DatabaseDependency,
    _csrf: LoginCSRFProtection,
) -> Response:
    """Authenticate using generic failure feedback and rotate any prior session."""

    form = await _login_credentials(request)
    settings: AppSettings = request.app.state.settings
    credentials = AuthService(database, settings).login(
        username=form.username,
        password=form.password,
        context=LoginContext(
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=getattr(request.state, "request_id", None),
            previous_session_token=request.cookies.get(settings.session_cookie_name),
        ),
    )
    if credentials is None:
        return _render_login(
            request,
            status_code=401,
            error=_GENERIC_LOGIN_ERROR,
            username=form.username.strip(),
        )

    response = RedirectResponse(url="/admin", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    _delete_login_csrf_cookie(response, settings)
    _set_session_cookie(response, settings, credentials.token)
    return response


@router.post("/logout", include_in_schema=False)
def logout(
    request: Request,
    database: DatabaseDependency,
    _admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Revoke the current server-side session and remove the browser cookie."""

    settings: AppSettings = request.app.state.settings
    SessionService(database, settings).revoke(
        request.cookies.get(settings.session_cookie_name),
        request_id=getattr(request.state, "request_id", None),
        ip_address=client_ip(request),
    )
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
        secure=settings.effective_session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_same_site,
    )
    return response
