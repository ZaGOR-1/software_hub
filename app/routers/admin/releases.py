"""Server-rendered release administration routes."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ApplicationError
from app.database.session import DatabaseDependency
from app.models.enums import ReleaseChannel, ReleaseStatus
from app.models.release import Release
from app.models.software import Software
from app.routers.admin.common import (
    enum_options,
    form_payload,
    form_values,
    redirect_admin,
    render_admin,
    request_audit_context,
)
from app.routers.auth.dependencies import CSRFProtectedAdminSession, RequiredAdminSession
from app.schemas.admin_forms import ReleaseAdminForm, validation_messages
from app.services.release_service import ReleaseService
from app.services.software_service import SoftwareService

router = APIRouter(prefix="/admin", tags=["admin-releases"])


def _release_form_response(
    request: Request,
    admin_session: RequiredAdminSession,
    *,
    software: Software,
    release: Release | None,
    values: dict[str, object] | None,
    errors: tuple[str, ...],
    status_code: int = 200,
) -> Response:
    return render_admin(
        request,
        admin_session,
        "admin/releases/form.html",
        status_code=status_code,
        software=software,
        release=release,
        channels=enum_options(ReleaseChannel),
        form_values=values,
        errors=errors,
    )


@router.get("/software/{software_id}/releases/new", include_in_schema=False)
def release_new_page(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render a new release form under one software entry."""

    software = SoftwareService(database).get(software_id)
    return _release_form_response(
        request,
        admin_session,
        software=software,
        release=None,
        values=None,
        errors=(),
    )


@router.post("/software/{software_id}/releases", include_in_schema=False)
async def release_create(
    software_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Create a draft release."""

    form = await request.form()
    values = form_values(form)
    software = SoftwareService(database).get(software_id)
    try:
        data = ReleaseAdminForm.model_validate(form_payload(form))
        release = ReleaseService(database).create(
            software_id=software_id,
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        return _release_form_response(
            request,
            admin_session,
            software=software,
            release=None,
            values=values,
            errors=validation_messages(exc),
            status_code=422,
        )
    except ApplicationError as exc:
        return _release_form_response(
            request,
            admin_session,
            software=software,
            release=None,
            values=values,
            errors=(exc.public_message,),
            status_code=int(exc.status_code),
        )
    return redirect_admin(
        f"/admin/releases/{release.id}/edit",
        notice="release-created",
    )


@router.get("/releases/{release_id}/edit", include_in_schema=False)
def release_edit_page(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render one release edit form."""

    release = ReleaseService(database).get(release_id)
    return _release_form_response(
        request,
        admin_session,
        software=release.software,
        release=release,
        values=None,
        errors=(),
    )


@router.post("/releases/{release_id}/edit", include_in_schema=False)
async def release_edit_submit(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Update one release."""

    form = await request.form()
    values = form_values(form)
    release = ReleaseService(database).get(release_id)
    try:
        data = ReleaseAdminForm.model_validate(form_payload(form))
        ReleaseService(database).update(
            release_id,
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        return _release_form_response(
            request,
            admin_session,
            software=release.software,
            release=release,
            values=values,
            errors=validation_messages(exc),
            status_code=422,
        )
    except ApplicationError as exc:
        return _release_form_response(
            request,
            admin_session,
            software=release.software,
            release=release,
            values=values,
            errors=(exc.public_message,),
            status_code=int(exc.status_code),
        )
    return redirect_admin(f"/admin/releases/{release_id}/edit", notice="release-updated")


def _release_transition(
    release_id: int,
    target: ReleaseStatus,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    release = ReleaseService(database).transition_status(
        release_id,
        target,
        audit=request_audit_context(request, database, admin_session),
    )
    return redirect_admin(
        f"/admin/software/{release.software_id}/preview",
        notice="release-status",
    )


@router.post("/releases/{release_id}/publish", include_in_schema=False)
def release_publish(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _release_transition(
        release_id,
        ReleaseStatus.PUBLISHED,
        request,
        database,
        admin_session,
    )


@router.post("/releases/{release_id}/archive", include_in_schema=False)
def release_archive(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _release_transition(
        release_id,
        ReleaseStatus.ARCHIVED,
        request,
        database,
        admin_session,
    )


@router.post("/releases/{release_id}/disable", include_in_schema=False)
def release_disable(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _release_transition(
        release_id,
        ReleaseStatus.DISABLED,
        request,
        database,
        admin_session,
    )


@router.post("/releases/{release_id}/restore", include_in_schema=False)
def release_restore(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    return _release_transition(
        release_id,
        ReleaseStatus.DRAFT,
        request,
        database,
        admin_session,
    )


@router.post("/releases/{release_id}/current", include_in_schema=False)
def release_set_current(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    release = ReleaseService(database).set_current_stable(
        release_id,
        audit=request_audit_context(request, database, admin_session),
    )
    return redirect_admin(
        f"/admin/software/{release.software_id}/preview",
        notice="release-current",
    )


@router.post("/releases/{release_id}/current/clear", include_in_schema=False)
def release_clear_current(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    release = ReleaseService(database).clear_current(
        release_id,
        audit=request_audit_context(request, database, admin_session),
    )
    return redirect_admin(
        f"/admin/software/{release.software_id}/preview",
        notice="release-current",
    )
