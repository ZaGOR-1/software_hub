"""Category persistence queries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


class CategoryRepository(BaseRepository[Category]):
    """Session-bound category CRUD and ordered listing."""

    model = Category

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_slug(self, slug: str) -> Category | None:
        """Return a category by its normalized slug."""

        statement = select(Category).where(Category.slug == slug.strip().casefold())
        return self.session.scalar(statement)

    def list_page(
        self,
        pagination: Pagination,
        *,
        visible_only: bool = False,
    ) -> Page[Category]:
        """Return categories in deterministic admin/public order."""

        statement = select(Category)
        if visible_only:
            statement = statement.where(Category.is_visible.is_(True))
        statement = statement.order_by(Category.sort_order, func.lower(Category.name), Category.id)
        return paginate_scalars(self.session, statement, pagination)
