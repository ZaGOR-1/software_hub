"""Shared helpers for server-rendered administration routes."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from starlette.datastructures import FormData
from starlette.templating import Jinja2Templates

from app.core.config import AppSettings
from app.core.csrf import CSRFTokenService
from app.database.session import Database
from app.routers.auth.dependencies import client_ip
from app.services.audit_service import AuditContext
from app.services.session_service import AuthenticatedSession, SessionService

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")

_NOTICE_MESSAGES = {
    "category-created": "Категорію створено.",
    "category-updated": "Категорію оновлено.",
    "category-deleted": "Категорію видалено.",
    "tag-created": "Тег створено.",
    "tag-updated": "Тег оновлено.",
    "tag-deleted": "Тег видалено.",
    "software-created": "Програму створено як чернетку.",
    "software-updated": "Дані програми оновлено.",
    "software-status": "Статус програми змінено.",
    "release-created": "Реліз створено як чернетку.",
    "release-updated": "Реліз оновлено.",
    "release-status": "Статус релізу змінено.",
    "release-current": "Поточний stable-реліз змінено.",
    "file-uploaded": "Файл перевірено та переміщено в quarantine.",
    "file-reviewed": "Рішення ручної перевірки збережено.",
    "file-verified": "Розмір і SHA-256 фізичного файла підтверджено.",
    "file-published": "Файл переміщено в permanent storage та опубліковано.",
    "file-disabled": "Файл вимкнено без фізичного видалення.",
    "file-archived": "Файл архівовано без фізичного видалення.",
    "file-restored": "Файл повернено в приватний стан ready.",
    "file-metadata-deleted": "Metadata видалено; фізичний файл збережено.",
    "file-permanently-deleted": "Metadata і фізичний файл остаточно видалено.",
}


def admin_context(
    request: Request,
    admin_session: AuthenticatedSession,
    **values: Any,
) -> dict[str, Any]:
    """Build the common template context without exposing session secrets."""

    settings: AppSettings = request.app.state.settings
    notice_key = request.query_params.get("notice")
    context: dict[str, Any] = {
        "admin_user": admin_session.user,
        "csrf_token": CSRFTokenService(settings).issue_session_token(
            admin_session.csrf_secret_hash
        ),
        "csrf_field_name": settings.csrf_form_field_name,
        "notice": _NOTICE_MESSAGES.get(notice_key or ""),
        "current_path": request.url.path,
    }
    context.update(values)
    return context


def render_admin(
    request: Request,
    admin_session: AuthenticatedSession,
    template_name: str,
    *,
    status_code: int = 200,
    **values: Any,
) -> Response:
    """Render an administration template with no-store caching."""

    response = TEMPLATES.TemplateResponse(
        request=request,
        name=template_name,
        context=admin_context(request, admin_session, **values),
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def redirect_admin(url: str, *, notice: str | None = None) -> RedirectResponse:
    """Return a PRG redirect with a fixed notice identifier."""

    target = url
    if notice is not None:
        separator = "&" if "?" in url else "?"
        target = f"{url}{separator}{urlencode({'notice': notice})}"
    response = RedirectResponse(url=target, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    return response


def form_payload(form: FormData, *, multi_fields: tuple[str, ...] = ()) -> dict[str, Any]:
    """Convert Starlette form data into a Pydantic-friendly bounded mapping."""

    payload: dict[str, Any] = dict(form.multi_items())
    for field in multi_fields:
        payload[field] = list(form.getlist(field))
    for checkbox in ("is_visible", "is_featured"):
        if checkbox in payload:
            payload[checkbox] = str(payload[checkbox]).lower() in {"1", "true", "on", "yes"}
    return payload


def form_values(form: FormData) -> dict[str, Any]:
    """Return escaped-by-Jinja form values for a failed submission."""

    values: dict[str, Any] = dict(form.multi_items())
    values["tag_ids"] = tuple(str(value) for value in form.getlist("tag_ids"))
    return values


def request_audit_context(
    request: Request,
    database: Database,
    admin_session: AuthenticatedSession,
) -> AuditContext:
    """Build a sanitized audit context for a state-changing admin request."""

    settings: AppSettings = request.app.state.settings
    ip_hash, _ = SessionService(database, settings).client_hashes(
        ip_address=client_ip(request),
        user_agent=None,
    )
    return AuditContext(
        user_id=admin_session.user.id,
        request_id=getattr(request.state, "request_id", None),
        ip_hash=ip_hash,
    )


def pagination_page(raw_page: str | None) -> int:
    """Parse a safe one-based page number for browser query parameters."""

    if raw_page is None:
        return 1
    try:
        page = int(raw_page)
    except ValueError:
        return 1
    return min(max(page, 1), 100_000)


def enum_options(enum_type: type[Enum]) -> tuple[Enum, ...]:
    """Expose enum members to templates without dynamic attribute access."""

    return tuple(enum_type)


def selected_ids(values: Mapping[str, Any] | None, fallback: tuple[int, ...]) -> set[str]:
    """Resolve selected checkbox IDs from form values or persisted metadata."""

    if values is None:
        return {str(value) for value in fallback}
    raw = values.get("tag_ids", ())
    if isinstance(raw, (list, tuple, set)):
        return {str(value) for value in raw}
    return {str(raw)} if raw not in {None, ""} else set()
