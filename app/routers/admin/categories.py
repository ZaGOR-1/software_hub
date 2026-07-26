"""Server-rendered category administration routes."""

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
from app.schemas.admin_forms import CategoryAdminForm, validation_messages
from app.schemas.pagination import Pagination
from app.services.category_service import CategoryService

router = APIRouter(prefix="/admin/categories", tags=["admin-categories"])


def _category_list_response(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
    *,
    status_code: int = 200,
    errors: tuple[str, ...] = (),
    values: dict[str, object] | None = None,
) -> Response:
    page_number = pagination_page(request.query_params.get("page"))
    page = CategoryService(database).list(Pagination(page=page_number, per_page=20))
    return render_admin(
        request,
        admin_session,
        "admin/categories/list.html",
        status_code=status_code,
        page=page,
        errors=errors,
        form_values=values or {},
    )


@router.get("", include_in_schema=False)
def category_list(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """List categories and show the create form."""

    return _category_list_response(request, database, admin_session)


@router.post("", include_in_schema=False)
async def category_create(
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Create a category from a CSRF-protected form."""

    form = await request.form()
    try:
        data = CategoryAdminForm.model_validate(form_payload(form))
        CategoryService(database).create(
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        return _category_list_response(
            request,
            database,
            admin_session,
            status_code=422,
            errors=validation_messages(exc),
            values=form_values(form),
        )
    except ApplicationError as exc:
        return _category_list_response(
            request,
            database,
            admin_session,
            status_code=int(exc.status_code),
            errors=(exc.public_message,),
            values=form_values(form),
        )
    return redirect_admin("/admin/categories", notice="category-created")


@router.get("/{category_id}/edit", include_in_schema=False)
def category_edit_page(
    category_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render one category edit form."""

    category = CategoryService(database).get(category_id)
    return render_admin(
        request,
        admin_session,
        "admin/categories/edit.html",
        category=category,
        errors=(),
        form_values=None,
    )


@router.post("/{category_id}/edit", include_in_schema=False)
async def category_edit_submit(
    category_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Update one category."""

    form = await request.form()
    try:
        data = CategoryAdminForm.model_validate(form_payload(form))
        CategoryService(database).update(
            category_id,
            **data.model_dump(),
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        category = CategoryService(database).get(category_id)
        return render_admin(
            request,
            admin_session,
            "admin/categories/edit.html",
            status_code=422,
            category=category,
            errors=validation_messages(exc),
            form_values=form_values(form),
        )
    except ApplicationError as exc:
        category = CategoryService(database).get(category_id)
        return render_admin(
            request,
            admin_session,
            "admin/categories/edit.html",
            status_code=int(exc.status_code),
            category=category,
            errors=(exc.public_message,),
            form_values=form_values(form),
        )
    return redirect_admin(f"/admin/categories/{category_id}/edit", notice="category-updated")


@router.post("/{category_id}/delete", include_in_schema=False)
async def category_delete(
    category_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    """Delete category metadata after explicit checkbox confirmation."""

    form = await request.form()
    if form.get("confirm") != "yes":
        raise ValidationError("Deletion confirmation is required.")
    CategoryService(database).delete(
        category_id,
        audit=request_audit_context(request, database, admin_session),
    )
    return redirect_admin("/admin/categories", notice="category-deleted")
