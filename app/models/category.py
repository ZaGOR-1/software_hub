"""Software category model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.mixins import TimestampMixin


class Category(TimestampMixin, Base):
    """Visible, sortable catalog category."""

    __tablename__ = "categories"
    __table_args__ = (CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )

    software: Mapped[list[Software]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )


if TYPE_CHECKING:
    from app.models.software import Software
