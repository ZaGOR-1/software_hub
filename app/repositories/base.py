"""Generic SQLAlchemy repository primitives."""

from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.schemas.pagination import Page, Pagination

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository[ModelT: Base]:
    """Small session-bound repository with explicit flush behavior."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: int) -> ModelT | None:
        """Return an entity by internal integer ID."""

        return self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        """Add and flush an entity without committing the transaction."""

        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Mark an entity for deletion without committing."""

        self.session.delete(entity)
        self.session.flush()

    def count(self) -> int:
        """Return the number of rows for this repository model."""

        value = self.session.scalar(select(func.count()).select_from(self.model))
        return int(value or 0)


def paginate_scalars[ModelT: Base](
    session: Session,
    statement: Select[tuple[ModelT]],
    pagination: Pagination,
) -> Page[ModelT]:
    """Apply safe pagination to a scalar select and return a total count."""

    count_source = statement.order_by(None).limit(None).offset(None).subquery()
    total = int(session.scalar(select(func.count()).select_from(count_source)) or 0)
    paged_statement = statement.limit(pagination.per_page).offset(pagination.offset)
    items: Sequence[ModelT] = tuple(session.scalars(paged_statement).unique().all())
    return Page(
        items=items,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )
