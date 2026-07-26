"""Tag persistence queries."""

from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


class TagRepository(BaseRepository[Tag]):
    """Session-bound tag CRUD and lookup operations."""

    model = Tag

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_slug(self, slug: str) -> Tag | None:
        """Return a tag by normalized slug."""

        statement = select(Tag).where(Tag.slug == slug.strip().casefold())
        return self.session.scalar(statement)

    def get_many(self, tag_ids: Collection[int]) -> list[Tag]:
        """Return unique tags for a collection of internal IDs."""

        unique_ids = tuple(dict.fromkeys(tag_ids))
        if not unique_ids:
            return []
        statement = select(Tag).where(Tag.id.in_(unique_ids)).order_by(Tag.id)
        return list(self.session.scalars(statement).all())

    def list_page(self, pagination: Pagination) -> Page[Tag]:
        """Return tags ordered by case-insensitive name."""

        statement = select(Tag).order_by(func.lower(Tag.name), Tag.id)
        return paginate_scalars(self.session, statement, pagination)
