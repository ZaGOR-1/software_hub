"""Server-rendered tag administration routes."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ApplicationError, ValidationError
from app.database.session import DatabaseDependency
from app.routers.admin.common import (
    form_payload,
    form_values,
    pagination_page,
    redirect_admin,
    render_admin,
    request_audit_context,
)
from app.routers.auth.dependencies import CSRFProtectedAdminSession, RequiredAdminSession
from app.schemas.admin_forms import TagAdminForm, validation_messages
from app.schemas.pagination import Pagination
from app.services.tag_service import TagService

router = APIRouter(prefix="/admin/tags", tags=["admin-tags"])


def _tag_list_response(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
    *,
    status_code: int = 200,
    errors: tuple[str, ...] = (),
    values: dict[str, object] | None = None,
) -> Response:
    page_number = pagination_page(request.query_params.get("page"))
    page = TagService(database).list(Pagination(page=page_number, per_page=30))
    return render_admin(
        request,
        admin_session,
        "admin/tags/list.html",
        status_code=status_code,
        page=page,
        errors=errors,
        form_values=values or {},
    )


@router.get("", include_in_schema=False)
def tag_list(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """List tags and show the create form."""

    return _tag_list_response(request, database, admin_session)


@router.post("", include_in_schema=False)
async def tag_create(
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Create a tag from a CSRF-protected form."""

    form = await request.form()
    try:
        data = TagAdminForm.model_validate(form_payload(form))
        TagService(database).create(
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        return _tag_list_response(
            request,
            database,
            admin_session,
            status_code=422,
            errors=validation_messages(exc),
            values=form_values(form),
        )
    except ApplicationError as exc:
        return _tag_list_response(
            request,
            database,
            admin_session,
            status_code=int(exc.status_code),
            errors=(exc.public_message,),
            values=form_values(form),
        )
    return redirect_admin("/admin/tags", notice="tag-created")


@router.get("/{tag_id}/edit", include_in_schema=False)
def tag_edit_page(
    tag_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render one tag edit form."""

    tag = TagService(database).get(tag_id)
    return render_admin(
        request,
        admin_session,
        "admin/tags/edit.html",
        tag=tag,
        errors=(),
        form_values=None,
    )


@router.post("/{tag_id}/edit", include_in_schema=False)
async def tag_edit_submit(
    tag_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Update one tag."""

    form = await request.form()
    try:
        data = TagAdminForm.model_validate(form_payload(form))
        TagService(database).update(
            tag_id,
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        tag = TagService(database).get(tag_id)
        return render_admin(
            request,
            admin_session,
            "admin/tags/edit.html",
            status_code=422,
            tag=tag,
            errors=validation_messages(exc),
            form_values=form_values(form),
        )
    except ApplicationError as exc:
        tag = TagService(database).get(tag_id)
        return render_admin(
            request,
            admin_session,
            "admin/tags/edit.html",
            status_code=int(exc.status_code),
            tag=tag,
            errors=(exc.public_message,),
            form_values=form_values(form),
        )
    return redirect_admin(f"/admin/tags/{tag_id}/edit", notice="tag-updated")


@router.post("/{tag_id}/delete", include_in_schema=False)
async def tag_delete(
    tag_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Delete tag metadata after explicit checkbox confirmation."""

    form = await request.form()
    if form.get("confirm") != "yes":
        raise ValidationError("Deletion confirmation is required.")
    TagService(database).delete(
        tag_id,
        audit=request_audit_context(request, database, admin_session),
    )
    return redirect_admin("/admin/tags", notice="tag-deleted")
