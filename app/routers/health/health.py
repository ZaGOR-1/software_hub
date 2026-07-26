"""Public readiness endpoint with bounded component states."""

import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.core.exceptions import ServiceUnavailable
from app.database.session import DatabaseDependency
from app.services.system_status_service import ComponentState, SystemStatusService
from app.storage.manager import StorageDependency

logger = logging.getLogger(__name__)


class HealthChecks(BaseModel):
    """Safe dependency states without capacity, paths or exception details."""

    application: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    storage: Literal["ok"] = "ok"
    disk: Literal["ok"] = "ok"


class HealthResponse(BaseModel):
    """Public readiness response without internal infrastructure details."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    checks: HealthChecks


router = APIRouter(tags=["health"])


@router.get("", response_model=HealthResponse, include_in_schema=True)
def health_check(
    database: DatabaseDependency,
    storage: StorageDependency,
) -> HealthResponse:
    """Confirm that process, database, storage and capacity are ready."""

    snapshot = SystemStatusService(database, storage).snapshot()
    if not snapshot.ready:
        failed_components = tuple(
            name
            for name, state in (
                ("database", snapshot.database.state),
                ("storage", snapshot.storage.state),
                ("disk", snapshot.disk.state),
            )
            if state is ComponentState.ERROR
        )
        logger.warning(
            "health_check_failed",
            extra={"failed_components": failed_components},
        )
        raise ServiceUnavailable("The service is not ready.")
    return HealthResponse(
        service="software-hub",
        version=__version__,
        checks=HealthChecks(),
    )
