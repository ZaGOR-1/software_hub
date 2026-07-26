"""Server-rendered software administration routes."""

from collections.abc import Sequence

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ApplicationError, ValidationError
from app.database.session import DatabaseDependency
from app.models.category import Category
from app.models.enums import SoftwareStatus, Visibility
from app.models.software import Software
from app.models.tag import Tag
from app.repositories.software_repository import SoftwareFilters, SoftwareSort
from app.routers.admin.common import (
    enum_options,
    form_payload,
    form_values,
    pagination_page,
    redirect_admin,
    render_admin,
    request_audit_context,
    selected_ids,
)
from app.routers.auth.dependencies import CSRFProtectedAdminSession, RequiredAdminSession
from app.schemas.admin_forms import SoftwareAdminForm, validation_messages
from app.schemas.pagination import Pagination
from app.services.category_service import CategoryService
from app.services.software_service import SoftwareService
from app.services.tag_service import TagService

router = APIRouter(prefix="/admin/software", tags=["admin-software"])


def _sanitize_form_values(values: dict[str, object]) -> dict[str, object]:
    """Avoid reflecting non-HTTP URL payloads back into browser form attributes."""

    sanitized = dict(values)
    for field in ("official_website_url", "source_url"):
        raw = sanitized.get(field)
        if isinstance(raw, str) and raw and not raw.lower().startswith(("http://", "https://")):
            sanitized[field] = ""
    return sanitized


def _metadata_options(
    database: DatabaseDependency,
) -> tuple[Sequence[Category], Sequence[Tag]]:
    categories = CategoryService(database).list(Pagination(page=1, per_page=100))
    tags = TagService(database).list(Pagination(page=1, per_page=100))
    return categories.items, tags.items


def _form_response(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
    *,
    software: Software | None,
    values: dict[str, object] | None,
    errors: tuple[str, ...],
    status_code: int = 200,
) -> Response:
    categories, tags = _metadata_options(database)
    fallback_ids = tuple(tag.id for tag in software.tags) if software is not None else ()
    return render_admin(
        request,
        admin_session,
        "admin/software/form.html",
        status_code=status_code,
        software=software,
        categories=categories,
        tags=tags,
        visibilities=enum_options(Visibility),
        selected_tag_ids=selected_ids(values, fallback_ids),
        form_values=values,
        errors=errors,
    )


def _parse_filters(request: Request) -> SoftwareFilters:
    statuses: tuple[SoftwareStatus, ...] = ()
    visibilities: tuple[Visibility, ...] = ()
    raw_status = request.query_params.get("status")
    raw_visibility = request.query_params.get("visibility")
    raw_sort = request.query_params.get("sort", SoftwareSort.UPDATED.value)
    try:
        if raw_status:
            statuses = (SoftwareStatus(raw_status),)
        if raw_visibility:
            visibilities = (Visibility(raw_visibility),)
        sort = SoftwareSort(raw_sort)
    except ValueError as exc:
        raise ValidationError("Invalid software filter.") from exc
    return SoftwareFilters(
        query=request.query_params.get("q"),
        statuses=statuses,
        visibilities=visibilities,
        sort=sort,
    )


@router.get("", include_in_schema=False)
def software_list(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """List and filter software records for administration."""

    page_number = pagination_page(request.query_params.get("page"))
    page = SoftwareService(database).list(
        Pagination(page=page_number, per_page=20),
        _parse_filters(request),
    )
    return render_admin(
        request,
        admin_session,
        "admin/software/list.html",
        page=page,
        statuses=enum_options(SoftwareStatus),
        visibilities=enum_options(Visibility),
        sorts=enum_options(SoftwareSort),
        filters={
            "q": request.query_params.get("q", ""),
            "status": request.query_params.get("status", ""),
            "visibility": request.query_params.get("visibility", ""),
            "sort": request.query_params.get("sort", SoftwareSort.UPDATED.value),
        },
    )


@router.get("/new", include_in_schema=False)
def software_new_page(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render the create software form."""

    return _form_response(
        request,
        database,
        admin_session,
        software=None,
        values=None,
        errors=(),
    )


@router.post("", include_in_schema=False)
async def software_create(
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Create draft software from a CSRF-protected form."""

    form = await request.form()
    values = _sanitize_form_values(form_values(form))
    try:
        data = SoftwareAdminForm.model_validate(form_payload(form, multi_fields=("tag_ids",)))
        software = SoftwareService(database).create(
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        return _form_response(
            request,
            database,
            admin_session,
            software=None,
            values=values,
            errors=validation_messages(exc),
            status_code=422,
        )
    except ApplicationError as exc:
        return _form_response(
            request,
            database,
            admin_session,
            software=None,
            values=values,
            errors=(exc.public_message,),
            status_code=int(exc.status_code),
        )
    return redirect_admin(
        f"/admin/software/{software.id}/preview",
        notice="software-created",
    )


@router.get("/{software_id}/preview", include_in_schema=False)
def software_preview(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render an administrator-only preview with release history."""

    software = SoftwareService(database).get(software_id)
    return render_admin(
        request,
        admin_session,
        "admin/software/preview.html",
        software=software,
        software_statuses=enum_options(SoftwareStatus),
    )


@router.get("/{software_id}/edit", include_in_schema=False)
def software_edit_page(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render one software edit form."""

    software = SoftwareService(database).get(software_id)
    return _form_response(
        request,
        database,
        admin_session,
        software=software,
        values=None,
        errors=(),
    )


@router.post("/{software_id}/edit", include_in_schema=False)
async def software_edit_submit(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Update editable software metadata."""

    form = await request.form()
    values = _sanitize_form_values(form_values(form))
    try:
        data = SoftwareAdminForm.model_validate(form_payload(form, multi_fields=("tag_ids",)))
        SoftwareService(database).update(
            software_id,
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        software = SoftwareService(database).get(software_id)
        return _form_response(
            request,
            database,
            admin_session,
            software=software,
            values=values,
            errors=validation_messages(exc),
            status_code=422,
        )
    except ApplicationError as exc:
        software = SoftwareService(database).get(software_id)
        return _form_response(
            request,
            database,
            admin_session,
            software=software,
            values=values,
            errors=(exc.public_message,),
            status_code=int(exc.status_code),
        )
    return redirect_admin(
        f"/admin/software/{software_id}/edit",
        notice="software-updated",
    )


def _software_transition(
    software_id: int,
    target: SoftwareStatus,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    SoftwareService(database).transition_status(
        software_id,
        target,
        audit=request_audit_context(request, database, admin_session),
    )
    return redirect_admin(
        f"/admin/software/{software_id}/preview",
        notice="software-status",
    )


@router.post("/{software_id}/publish", include_in_schema=False)
def software_publish(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _software_transition(
        software_id,
        SoftwareStatus.PUBLISHED,
        request,
        database,
        admin_session,
    )


@router.post("/{software_id}/hide", include_in_schema=False)
def software_hide(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _software_transition(
        software_id,
        SoftwareStatus.HIDDEN,
        request,
        database,
        admin_session,
    )


@router.post("/{software_id}/archive", include_in_schema=False)
def software_archive(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _software_transition(
        software_id,
        SoftwareStatus.ARCHIVED,
        request,
        database,
        admin_session,
    )


@router.post("/{software_id}/disable", include_in_schema=False)
def software_disable(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _software_transition(
        software_id,
        SoftwareStatus.DISABLED,
        request,
        database,
        admin_session,
    )


@router.post("/{software_id}/restore", include_in_schema=False)
def software_restore(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _software_transition(
        software_id,
        SoftwareStatus.DRAFT,
        request,
        database,
        admin_session,
    )
