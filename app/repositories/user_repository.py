"""Administrator user persistence queries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Session-bound access to administrator accounts."""

    model = User

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_username(self, username: str) -> User | None:
        """Resolve a normalized username case-insensitively."""

        normalized = username.strip().casefold()
        statement = select(User).where(func.lower(User.username) == normalized)
        return self.session.scalar(statement)
