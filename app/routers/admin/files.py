"""Server-rendered release-file upload and quarantine inspection routes."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import ValidationError as PydanticValidationError
from starlette.datastructures import FormData, UploadFile

from app.core.config import AppSettings
from app.core.exceptions import ApplicationError, ValidationError
from app.database.session import DatabaseDependency
from app.models.enums import Architecture, FileStatus, PackageType, Visibility
from app.models.release import Release
from app.models.release_file import ReleaseFile
from app.routers.admin.common import (
    enum_options,
    redirect_admin,
    render_admin,
    request_audit_context,
)
from app.routers.auth.dependencies import (
    CSRFProtectedAdminSession,
    RequiredAdminSession,
    UploadCSRFProtectedAdminSession,
)
from app.schemas.admin_forms import ReleaseFileUploadForm, validation_messages
from app.services.audit_service import AuditContext
from app.services.file_service import FileService
from app.services.release_service import ReleaseService
from app.services.upload_service import UploadMetadata, UploadService
from app.storage.manager import StorageDependency
from app.storage.scanner import ScannerDependency
from app.storage.validation import assess_stored_signature

router = APIRouter(prefix="/admin", tags=["admin-files"])


def _metadata_values(form: FormData, *, csrf_field_name: str) -> dict[str, str]:
    """Return value-only upload metadata without retaining an UploadFile object."""

    return {
        key: value
        for key, value in form.multi_items()
        if isinstance(value, str) and key != csrf_field_name
    }


def _upload_form_response(
    request: Request,
    admin_session: RequiredAdminSession,
    *,
    release: Release,
    values: dict[str, str] | None,
    errors: tuple[str, ...],
    status_code: int = 200,
) -> Response:
    return render_admin(
        request,
        admin_session,
        "admin/files/new.html",
        status_code=status_code,
        release=release,
        software=release.software,
        architectures=enum_options(Architecture),
        package_types=enum_options(PackageType),
        visibilities=enum_options(Visibility),
        form_values=values,
        errors=errors,
    )


@router.get("/releases/{release_id}/files/new", include_in_schema=False)
def file_upload_page(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render the private release-file upload form."""

    release = ReleaseService(database).get(release_id)
    return _upload_form_response(
        request,
        admin_session,
        release=release,
        values=None,
        errors=(),
    )


@router.post("/releases/{release_id}/files", include_in_schema=False)
async def file_upload_submit(
    release_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    scanner: ScannerDependency,
    admin_session: UploadCSRFProtectedAdminSession,
) -> Response:
    """Stream one validated file into quarantine and create metadata."""

    form = await request.form()
    settings: AppSettings = request.app.state.settings
    values = _metadata_values(form, csrf_field_name=settings.csrf_form_field_name)
    release = ReleaseService(database).get(release_id)
    raw_upload = form.get("file")
    if not isinstance(raw_upload, UploadFile):
        return _upload_form_response(
            request,
            admin_session,
            release=release,
            values=values,
            errors=("Виберіть файл для завантаження.",),
            status_code=422,
        )

    handed_to_service = False
    try:
        data = ReleaseFileUploadForm.model_validate(values)
        handed_to_service = True
        metadata = UploadMetadata(
            display_filename=data.display_filename,
            architecture=data.architecture,
            package_type=data.package_type,
            platform=data.platform,
            edition=data.edition,
            visibility=data.visibility,
            source_url=data.source_url,
            admin_note=data.admin_note,
        )
        release_file = await UploadService(database, settings).upload_release_file(
            release_id=release_id,
            upload=raw_upload,
            metadata=metadata,
            storage=storage,
            scanner=scanner,
            audit=request_audit_context(request, database, admin_session),
        )
    except PydanticValidationError as exc:
        return _upload_form_response(
            request,
            admin_session,
            release=release,
            values=values,
            errors=validation_messages(exc),
            status_code=422,
        )
    except ApplicationError as exc:
        return _upload_form_response(
            request,
            admin_session,
            release=release,
            values=values,
            errors=(exc.public_message,),
            status_code=int(exc.status_code),
        )
    finally:
        if not handed_to_service:
            await raw_upload.close()

    return redirect_admin(f"/admin/files/{release_file.id}", notice="file-uploaded")


@router.get("/files/{file_id}", include_in_schema=False)
def file_detail_page(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Display validation, storage and lifecycle metadata for one private file."""

    service = FileService(database)
    release_file: ReleaseFile = service.get(file_id)
    duplicates = service.find_duplicates(release_file.sha256, exclude_file_id=file_id)
    settings: AppSettings = request.app.state.settings
    public_url = (
        f"{str(settings.public_base_url).rstrip('/')}/download/"
        f"{release_file.public_uuid}/{quote(release_file.display_filename)}"
    )
    return render_admin(
        request,
        admin_session,
        "admin/files/detail.html",
        release_file=release_file,
        release=release_file.release,
        software=release_file.release.software,
        duplicates=duplicates,
        storage_state=service.storage_state(file_id, storage),
        public_url=public_url,
        magic_assessment=assess_stored_signature(
            release_file.file_extension,
            release_file.detected_mime_type,
        ),
    )


def _audit(
    request: Request,
    database: DatabaseDependency,
    admin_session: RequiredAdminSession,
) -> AuditContext:
    return request_audit_context(request, database, admin_session)


@router.post("/files/{file_id}/review/approve", include_in_schema=False)
def file_review_approve(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).review_status(
        file_id,
        FileStatus.READY,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-reviewed")


@router.post("/files/{file_id}/review/reject", include_in_schema=False)
def file_review_reject(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).review_status(
        file_id,
        FileStatus.REJECTED,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-reviewed")


@router.post("/files/{file_id}/review/reopen", include_in_schema=False)
def file_review_reopen(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).review_status(
        file_id,
        FileStatus.QUARANTINE,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-reviewed")


@router.post("/files/{file_id}/verify", include_in_schema=False)
def file_verify(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).verify_integrity(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-verified")


@router.post("/files/{file_id}/publish", include_in_schema=False)
def file_publish(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).publish(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-published")


@router.post("/files/{file_id}/disable", include_in_schema=False)
def file_disable(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).disable(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-disabled")


@router.post("/files/{file_id}/archive", include_in_schema=False)
def file_archive(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).archive(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-archived")


@router.post("/files/{file_id}/restore", include_in_schema=False)
def file_restore(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    FileService(database).restore_ready(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(f"/admin/files/{file_id}", notice="file-restored")


async def _confirmation(request: Request, expected: str) -> None:
    form = await request.form()
    if form.get("confirmation") != expected:
        raise ValidationError(f'Type "{expected}" to confirm this destructive action.')


@router.post("/files/{file_id}/delete-metadata", include_in_schema=False)
async def file_delete_metadata(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    await _confirmation(request, "DELETE METADATA")
    result = FileService(database).delete_metadata(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(
        f"/admin/releases/{result.release_id}/edit",
        notice="file-metadata-deleted",
    )


@router.post("/files/{file_id}/delete-permanently", include_in_schema=False)
async def file_delete_permanently(
    file_id: int,
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: CSRFProtectedAdminSession,
) -> Response:
    await _confirmation(request, "DELETE FILE")
    result = FileService(database).permanently_delete(
        file_id,
        storage,
        audit=_audit(request, database, admin_session),
    )
    return redirect_admin(
        f"/admin/releases/{result.release_id}/edit",
        notice="file-permanently-deleted",
    )
