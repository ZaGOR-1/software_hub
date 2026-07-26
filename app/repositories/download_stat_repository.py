"""Daily download statistic persistence queries."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.download_stat import DownloadStat
from app.models.release_file import ReleaseFile
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


@dataclass(frozen=True, slots=True)
class DailyDownloadTotals:
    """Privacy-preserving aggregate totals for one UTC calendar day."""

    authorized: int
    successful: int
    blocked: int


class DownloadStatRepository(BaseRepository[DownloadStat]):
    """Session-bound daily aggregate lookups and atomic counter updates."""

    model = DownloadStat

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_for_date(self, release_file_id: int, day: date) -> DownloadStat | None:
        """Return the aggregate row for one file and UTC calendar day."""

        statement = select(DownloadStat).where(
            DownloadStat.release_file_id == release_file_id,
            DownloadStat.date == day,
        )
        return self.session.scalar(statement)

    def list_for_file(
        self,
        release_file_id: int,
        pagination: Pagination,
    ) -> Page[DownloadStat]:
        """Return newest daily aggregates first."""

        statement = (
            select(DownloadStat)
            .where(DownloadStat.release_file_id == release_file_id)
            .order_by(DownloadStat.date.desc())
        )
        return paginate_scalars(self.session, statement, pagination)

    def totals_for_date(self, day: date) -> DailyDownloadTotals:
        """Return bounded aggregate counters for one day."""

        row = self.session.execute(
            select(
                func.coalesce(func.sum(DownloadStat.download_count), 0),
                func.coalesce(func.sum(DownloadStat.successful_download_count), 0),
                func.coalesce(func.sum(DownloadStat.blocked_download_count), 0),
            ).where(DownloadStat.date == day)
        ).one()
        return DailyDownloadTotals(
            authorized=int(row[0]),
            successful=int(row[1]),
            blocked=int(row[2]),
        )

    def record_authorized_start(self, release_file_id: int, day: date) -> None:
        """Atomically increment the file total and daily authorized-start counters."""

        self.session.execute(
            update(ReleaseFile)
            .where(ReleaseFile.id == release_file_id)
            .values(download_count=ReleaseFile.download_count + 1)
        )
        self._upsert_daily(
            release_file_id,
            day,
            download_increment=1,
            successful_increment=1,
            blocked_increment=0,
        )

    def record_blocked(self, release_file_id: int, day: date) -> None:
        """Increment only the daily blocked-attempt counter."""

        self._upsert_daily(
            release_file_id,
            day,
            download_increment=0,
            successful_increment=0,
            blocked_increment=1,
        )

    def _upsert_daily(
        self,
        release_file_id: int,
        day: date,
        *,
        download_increment: int,
        successful_increment: int,
        blocked_increment: int,
    ) -> None:
        bind = self.session.get_bind()
        if bind.dialect.name == "sqlite":
            statement = sqlite_insert(DownloadStat).values(
                release_file_id=release_file_id,
                date=day,
                download_count=download_increment,
                successful_download_count=successful_increment,
                blocked_download_count=blocked_increment,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[DownloadStat.release_file_id, DownloadStat.date],
                set_={
                    "download_count": DownloadStat.download_count + download_increment,
                    "successful_download_count": (
                        DownloadStat.successful_download_count + successful_increment
                    ),
                    "blocked_download_count": (
                        DownloadStat.blocked_download_count + blocked_increment
                    ),
                },
            )
            self.session.execute(statement)
            return

        current = self.get_for_date(release_file_id, day)
        if current is None:
            self.add(
                DownloadStat(
                    release_file_id=release_file_id,
                    date=day,
                    download_count=download_increment,
                    successful_download_count=successful_increment,
                    blocked_download_count=blocked_increment,
                )
            )
            return
        current.download_count += download_increment
        current.successful_download_count += successful_increment
        current.blocked_download_count += blocked_increment
        self.session.flush()
