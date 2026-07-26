"""Bounded administration dashboard metrics and operational status."""

from dataclasses import dataclass

from app.core.time import utc_now
from app.database.session import Database
from app.models.audit_log import AuditLog
from app.models.enums import FileStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.download_stat_repository import DailyDownloadTotals, DownloadStatRepository
from app.repositories.release_file_repository import ReleaseFileRepository
from app.repositories.release_repository import ReleaseRepository
from app.repositories.software_repository import SoftwareRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.pagination import Pagination
from app.services.system_status_service import SystemStatusService, SystemStatusSnapshot
from app.storage.manager import StorageManager


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Bounded catalog counters, downloads, audit and infrastructure status."""

    software_count: int
    release_count: int
    file_count: int
    category_count: int
    tag_count: int
    total_downloads: int
    downloads_today: int
    blocked_today: int
    quarantine_count: int
    disabled_count: int
    recent_audit: tuple[AuditLog, ...]
    system: SystemStatusSnapshot


class DashboardService:
    """Collect inexpensive dashboard data with bounded queries."""

    def __init__(self, database: Database, storage: StorageManager) -> None:
        self.database = database
        self.storage = storage

    def snapshot(self) -> DashboardSnapshot:
        """Return counters, ten newest audit events and operational status."""

        with self.database.session() as session:
            recent = AuditRepository(session).list_page(Pagination(page=1, per_page=10))
            file_repository = ReleaseFileRepository(session)
            daily: DailyDownloadTotals = DownloadStatRepository(session).totals_for_date(
                utc_now().date()
            )
            snapshot = DashboardSnapshot(
                software_count=SoftwareRepository(session).count(),
                release_count=ReleaseRepository(session).count(),
                file_count=file_repository.count(),
                category_count=CategoryRepository(session).count(),
                tag_count=TagRepository(session).count(),
                total_downloads=file_repository.total_downloads(),
                downloads_today=daily.authorized,
                blocked_today=daily.blocked,
                quarantine_count=file_repository.count_by_statuses(
                    (FileStatus.QUARANTINE, FileStatus.READY, FileStatus.REJECTED)
                ),
                disabled_count=file_repository.count_by_statuses((FileStatus.DISABLED,)),
                recent_audit=tuple(recent.items),
                system=SystemStatusService(self.database, self.storage).snapshot(),
            )
            return snapshot
