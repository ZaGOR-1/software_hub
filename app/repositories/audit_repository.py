"""Append-only audit log persistence queries."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import distinct, select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


@dataclass(frozen=True, slots=True)
class AuditUserOption:
    """Minimal administrator identity displayed in audit filters."""

    id: int
    username: str


class AuditRepository(BaseRepository[AuditLog]):
    """Session-bound append and filtered audit listing."""

    model = AuditLog

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def list_page(
        self,
        pagination: Pagination,
        *,
        action: str | None = None,
        result: str | None = None,
        user_id: int | None = None,
        entity_type: str | None = None,
        started_at: datetime | None = None,
        ended_before: datetime | None = None,
    ) -> Page[AuditLog]:
        """Return eagerly loaded audit records with bind-parameter filters."""

        statement = select(AuditLog).options(selectinload(AuditLog.user))
        if action is not None:
            statement = statement.where(AuditLog.action == action)
        if result is not None:
            statement = statement.where(AuditLog.result == result)
        if user_id is not None:
            statement = statement.where(AuditLog.user_id == user_id)
        if entity_type is not None:
            statement = statement.where(AuditLog.entity_type == entity_type)
        if started_at is not None:
            statement = statement.where(AuditLog.timestamp >= started_at)
        if ended_before is not None:
            statement = statement.where(AuditLog.timestamp < ended_before)
        statement = statement.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        return paginate_scalars(self.session, statement, pagination)

    def list_entity_types(self, *, limit: int) -> tuple[str, ...]:
        """Return a bounded list of entity types already present in the log."""

        statement = (
            select(distinct(AuditLog.entity_type))
            .where(AuditLog.entity_type.is_not(None))
            .order_by(AuditLog.entity_type)
            .limit(limit)
        )
        return tuple(str(value) for value in self.session.scalars(statement).all())

    def list_user_options(self, *, limit: int) -> tuple[AuditUserOption, ...]:
        """Return administrators referenced by at least one audit record."""

        statement = (
            select(User.id, User.username)
            .join(AuditLog, AuditLog.user_id == User.id)
            .distinct()
            .order_by(User.username, User.id)
            .limit(limit)
        )
        return tuple(
            AuditUserOption(id=int(user_id), username=str(username))
            for user_id, username in self.session.execute(statement).all()
        )
