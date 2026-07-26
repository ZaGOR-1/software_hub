"""Protected administration dashboard routes."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.database.session import DatabaseDependency
from app.routers.admin.common import render_admin
from app.routers.auth.dependencies import RequiredAdminSession
from app.services.dashboard_service import DashboardService
from app.storage.manager import StorageDependency

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", include_in_schema=False)
def admin_dashboard(
    request: Request,
    database: DatabaseDependency,
    storage: StorageDependency,
    admin_session: RequiredAdminSession,
) -> Response:
    """Render the authenticated administration dashboard."""

    return render_admin(
        request,
        admin_session,
        "admin/dashboard.html",
        snapshot=DashboardService(database, storage).snapshot(),
    )
