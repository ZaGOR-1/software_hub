"""Top-level software catalog model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UTCDateTime
from app.models.associations import software_tags
from app.models.enums import SoftwareStatus, Visibility
from app.models.mixins import TimestampMixin
from app.models.types import enum_type


class Software(TimestampMixin, Base):
    """Catalog entry that owns releases and downloadable files."""

    __tablename__ = "software"
    __table_args__ = (
        Index("ix_software_public_listing", "status", "visibility", "updated_at"),
        Index("ix_software_category_status", "category_id", "status"),
        Index("ix_software_featured_updated", "is_featured", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(500), nullable=False)
    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    developer_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    official_website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    icon_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supported_os: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SoftwareStatus] = mapped_column(
        enum_type(SoftwareStatus, name="software_status"),
        nullable=False,
        default=SoftwareStatus.DRAFT,
        server_default=SoftwareStatus.DRAFT.value,
        index=True,
    )
    visibility: Mapped[Visibility] = mapped_column(
        enum_type(Visibility, name="software_visibility"),
        nullable=False,
        default=Visibility.PRIVATE,
        server_default=Visibility.PRIVATE.value,
        index=True,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    category: Mapped[Category | None] = relationship(back_populates="software")
    tags: Mapped[list[Tag]] = relationship(
        secondary=software_tags,
        back_populates="software",
        passive_deletes=True,
    )
    releases: Mapped[list[Release]] = relationship(
        back_populates="software",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Release.release_date.desc()",
    )


if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.release import Release
    from app.models.tag import Tag
