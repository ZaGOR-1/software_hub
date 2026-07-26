"""Authenticated audit log browser with bounded filters and pagination."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.database.session import DatabaseDependency
from app.routers.admin.common import pagination_page, render_admin
from app.routers.auth.dependencies import RequiredAdminSession
from app.schemas.pagination import Pagination
from app.services.audit_service import AuditFilters, AuditResult, AuditService

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


def _date_bounds(
    raw_start: str | None,
    raw_end: str | None,
) -> tuple[datetime | None, datetime | None, tuple[str, ...]]:
    errors: list[str] = []
    started_at: datetime | None = None
    ended_before: datetime | None = None
    if raw_start:
        try:
            started_at = datetime.combine(date.fromisoformat(raw_start), time.min, tzinfo=UTC)
        except ValueError:
            errors.append("Дата початку має бути у форматі РРРР-ММ-ДД.")
    if raw_end:
        try:
            end_date = date.fromisoformat(raw_end)
            ended_before = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        except ValueError:
            errors.append("Дата завершення має бути у форматі РРРР-ММ-ДД.")
    if started_at is not None and ended_before is not None and started_at >= ended_before:
        errors.append("Дата початку не може бути пізнішою за дату завершення.")
    return started_at, ended_before, tuple(errors)


def _optional_positive_int(raw: str | None) -> int | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _result(raw: str | None) -> AuditResult | None:
    if raw is None or not raw:
        return None
    try:
        return AuditResult(raw)
    except ValueError:
        return None


def _page_url(request: Request, page: int) -> str:
    values = dict(request.query_params)
    values["page"] = str(page)
    return f"/admin/audit?{urlencode(values)}"


@router.get("", include_in_schema=False)
def audit_log(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render a filtered, eagerly loaded and bounded audit page."""

    raw_start = request.query_params.get("date_from")
    raw_end = request.query_params.get("date_to")
    started_at, ended_before, errors = _date_bounds(raw_start, raw_end)
    filters = AuditFilters(
        action=request.query_params.get("action") or None,
        result=_result(request.query_params.get("result")),
        user_id=_optional_positive_int(request.query_params.get("user_id")),
        entity_type=request.query_params.get("entity_type") or None,
        started_at=started_at,
        ended_before=ended_before,
    )
    page_number = pagination_page(request.query_params.get("page"))
    snapshot = AuditService(database).list_page(
        Pagination(page=page_number, per_page=50),
        filters,
    )
    previous_url = _page_url(request, page_number - 1) if snapshot.page.has_previous else None
    next_url = _page_url(request, page_number + 1) if snapshot.page.has_next else None
    return render_admin(
        request,
        admin_session,
        "admin/audit/index.html",
        status_code=422 if errors else 200,
        snapshot=snapshot,
        filter_values={
            "action": filters.action or "",
            "result": filters.result.value if filters.result is not None else "",
            "user_id": str(filters.user_id or ""),
            "entity_type": filters.entity_type or "",
            "date_from": raw_start or "",
            "date_to": raw_end or "",
        },
        errors=errors,
        previous_url=previous_url,
        next_url=next_url,
    )
