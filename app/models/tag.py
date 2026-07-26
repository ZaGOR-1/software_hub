"""Software tag model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.associations import software_tags
from app.models.mixins import TimestampMixin


class Tag(TimestampMixin, Base):
    """Reusable catalog tag."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)

    software: Mapped[list[Software]] = relationship(
        secondary=software_tags,
        back_populates="tags",
        passive_deletes=True,
    )


if TYPE_CHECKING:
    from app.models.software import Software
