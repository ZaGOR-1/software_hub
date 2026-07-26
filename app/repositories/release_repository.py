"""Software release persistence queries."""

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ReleaseChannel
from app.models.release import Release
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


class ReleaseRepository(BaseRepository[Release]):
    """Session-bound release CRUD and current-release operations."""

    model = Release

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_with_graph(self, release_id: int, *, for_update: bool = False) -> Release | None:
        """Return a release with its software and files eagerly loaded."""

        statement = (
            select(Release)
            .where(Release.id == release_id)
            .options(selectinload(Release.software), selectinload(Release.files))
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_by_identity(
        self,
        software_id: int,
        version: str,
        release_channel: ReleaseChannel,
    ) -> Release | None:
        """Return a release by its software/version/channel identity."""

        statement = select(Release).where(
            Release.software_id == software_id,
            Release.version == version,
            Release.release_channel == release_channel,
        )
        return self.session.scalar(statement)

    def list_for_software(
        self,
        software_id: int,
        pagination: Pagination,
    ) -> Page[Release]:
        """Return releases for one software entry in newest-first order."""

        statement = (
            select(Release)
            .where(Release.software_id == software_id)
            .options(selectinload(Release.files))
            .order_by(Release.release_date.desc().nullslast(), Release.id.desc())
        )
        return paginate_scalars(self.session, statement, pagination)

    def get_current_stable(self, software_id: int) -> Release | None:
        """Return the one current stable release for a software entry."""

        statement = select(Release).where(
            Release.software_id == software_id,
            Release.release_channel == ReleaseChannel.STABLE,
            Release.is_current.is_(True),
        )
        return self.session.scalar(statement)

    def clear_current_stable(self, software_id: int, *, except_release_id: int) -> int:
        """Clear current markers from all other stable releases atomically."""

        statement = (
            update(Release)
            .where(
                Release.software_id == software_id,
                Release.release_channel == ReleaseChannel.STABLE,
                Release.id != except_release_id,
                Release.is_current.is_(True),
            )
            .values(is_current=False)
        )
        result = cast(CursorResult[Any], self.session.execute(statement))
        return int(result.rowcount or 0)
