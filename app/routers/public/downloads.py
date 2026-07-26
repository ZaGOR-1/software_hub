"""Public and administrator-authorized Nginx-backed download routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request
from fastapi.responses import Response

from app.database.session import DatabaseDependency
from app.routers.auth.dependencies import OptionalAdminSession
from app.services.download_service import DownloadGrant, DownloadService
from app.storage.manager import StorageDependency

router = APIRouter(tags=["downloads"])


def _download_response(grant: DownloadGrant) -> Response:
    headers = {
        "X-Accel-Redirect": grant.internal_redirect_uri,
        "Content-Disposition": grant.content_disposition,
        "Content-Type": grant.content_type,
        "Accept-Ranges": "bytes",
        "ETag": grant.etag,
        "Cache-Control": grant.cache_control,
    }
    return Response(content=b"", status_code=200, headers=headers)


def _authorize(
    *,
    request: Request,
    public_uuid: UUID,
    safe_filename: str,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: OptionalAdminSession,
    count_download: bool,
) -> DownloadGrant:
    return DownloadService(database, request.app.state.settings).authorize(
        public_uuid=public_uuid,
        requested_filename=safe_filename,
        storage=storage,
        is_admin=admin_session is not None,
        count_download=count_download,
    )


@router.get("/download/{public_uuid}/{safe_filename}", include_in_schema=False)
def download_file(
    public_uuid: UUID,
    safe_filename: Annotated[str, Path(min_length=1, max_length=255)],
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Authorize a GET and delegate the body to Nginx via X-Accel-Redirect."""

    return _download_response(
        _authorize(
            request=request,
            public_uuid=public_uuid,
            safe_filename=safe_filename,
            database=database,
            storage=storage,
            admin_session=admin_session,
            count_download=True,
        )
    )


@router.head("/download/{public_uuid}/{safe_filename}", include_in_schema=False)
def download_file_head(
    public_uuid: UUID,
    safe_filename: Annotated[str, Path(min_length=1, max_length=255)],
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Authorize metadata lookup without incrementing download counters."""

    return _download_response(
        _authorize(
            request=request,
            public_uuid=public_uuid,
            safe_filename=safe_filename,
            database=database,
            storage=storage,
            admin_session=admin_session,
            count_download=False,
        )
    )
