"""Release file metadata persistence queries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FileStatus
from app.models.release import Release
from app.models.release_file import ReleaseFile
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


class ReleaseFileRepository(BaseRepository[ReleaseFile]):
    """Session-bound release-file CRUD and duplicate detection."""

    model = ReleaseFile

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_with_graph(self, file_id: int, *, for_update: bool = False) -> ReleaseFile | None:
        """Return a file with its release and software eagerly loaded."""

        statement = (
            select(ReleaseFile)
            .where(ReleaseFile.id == file_id)
            .options(selectinload(ReleaseFile.release).selectinload(Release.software))
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_by_public_uuid(self, public_uuid: UUID) -> ReleaseFile | None:
        """Resolve a public UUID with all authorization metadata loaded."""

        statement = (
            select(ReleaseFile)
            .where(ReleaseFile.public_uuid == public_uuid)
            .options(selectinload(ReleaseFile.release).selectinload(Release.software))
        )
        return self.session.scalar(statement)

    def find_by_sha256(
        self,
        sha256: str,
        *,
        exclude_file_id: int | None = None,
    ) -> list[ReleaseFile]:
        """Return files with the same normalized SHA-256 digest."""

        statement = (
            select(ReleaseFile)
            .where(ReleaseFile.sha256 == sha256.strip().casefold())
            .options(selectinload(ReleaseFile.release).selectinload(Release.software))
        )
        if exclude_file_id is not None:
            statement = statement.where(ReleaseFile.id != exclude_file_id)
        statement = statement.order_by(ReleaseFile.id)
        return list(self.session.scalars(statement).all())

    def count_by_statuses(self, statuses: tuple[FileStatus, ...]) -> int:
        """Return the number of files in a bounded set of lifecycle states."""

        if not statuses:
            return 0
        value = self.session.scalar(
            select(func.count()).select_from(ReleaseFile).where(ReleaseFile.status.in_(statuses))
        )
        return int(value or 0)

    def total_downloads(self) -> int:
        """Return the denormalized authorized download-start total."""

        value = self.session.scalar(select(func.coalesce(func.sum(ReleaseFile.download_count), 0)))
        return int(value or 0)

    def list_for_release(
        self,
        release_id: int,
        pagination: Pagination,
    ) -> Page[ReleaseFile]:
        """Return files for a release in upload order."""

        statement = (
            select(ReleaseFile)
            .where(ReleaseFile.release_id == release_id)
            .order_by(ReleaseFile.uploaded_at.desc(), ReleaseFile.id.desc())
        )
        return paginate_scalars(self.session, statement, pagination)
