"""Software release model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.types import UTCDateTime
from app.models.enums import ReleaseChannel, ReleaseStatus
from app.models.mixins import TimestampMixin
from app.models.types import enum_type


class Release(TimestampMixin, Base):
    """Versioned software release containing one or more files."""

    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint(
            "software_id",
            "version",
            "release_channel",
            name="uq_releases_software_version_channel",
        ),
        Index("ix_releases_software_status", "software_id", "status"),
        Index("ix_releases_software_date", "software_id", "release_date"),
        Index(
            "uq_releases_one_current_stable_per_software",
            "software_id",
            unique=True,
            sqlite_where=text("is_current = 1 AND release_channel = 'stable'"),
            postgresql_where=text("is_current IS TRUE AND release_channel = 'stable'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    software_id: Mapped[int] = mapped_column(
        ForeignKey("software.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    release_channel: Mapped[ReleaseChannel] = mapped_column(
        enum_type(ReleaseChannel, name="release_channel"),
        nullable=False,
        default=ReleaseChannel.STABLE,
        server_default=ReleaseChannel.STABLE.value,
    )
    release_date: Mapped[date | None] = mapped_column(nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    status: Mapped[ReleaseStatus] = mapped_column(
        enum_type(ReleaseStatus, name="release_status"),
        nullable=False,
        default=ReleaseStatus.DRAFT,
        server_default=ReleaseStatus.DRAFT.value,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    software: Mapped[Software] = relationship(back_populates="releases")
    files: Mapped[list[ReleaseFile]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


if TYPE_CHECKING:
    from app.models.release_file import ReleaseFile
    from app.models.software import Software
