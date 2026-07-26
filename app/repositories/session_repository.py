"""Server-side session persistence queries."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, selectinload

from app.models.session import UserSession
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[UserSession]):
    """Session-bound access to hashed administrator sessions."""

    model = UserSession

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        """Return one session and its user by the persisted token hash."""

        statement = (
            select(UserSession)
            .where(UserSession.session_token_hash == token_hash)
            .options(selectinload(UserSession.user))
        )
        return self.session.scalar(statement)

    def revoke_all_for_user(
        self,
        user_id: int,
        *,
        now: datetime,
        except_session_id: int | None = None,
    ) -> int:
        """Revoke every active session for a user, optionally preserving one."""

        statement = update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if except_session_id is not None:
            statement = statement.where(UserSession.id != except_session_id)
        result = cast(CursorResult[Any], self.session.execute(statement.values(revoked_at=now)))
        return int(result.rowcount or 0)

    def delete_expired(self, now: datetime) -> int:
        """Delete sessions whose idle or absolute lifetime has elapsed."""

        statement = delete(UserSession).where(
            (UserSession.expires_at <= now) | (UserSession.absolute_expires_at <= now)
        )
        result = cast(CursorResult[Any], self.session.execute(statement))
        return int(result.rowcount or 0)
