"""Daily aggregated download statistics."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DownloadStat(Base):
    """Privacy-preserving daily counters for one release file."""

    __tablename__ = "download_stats"
    __table_args__ = (
        UniqueConstraint("release_file_id", "date", name="uq_download_stats_file_date"),
        CheckConstraint("download_count >= 0", name="download_count_nonnegative"),
        CheckConstraint("successful_download_count >= 0", name="successful_count_nonnegative"),
        CheckConstraint("blocked_download_count >= 0", name="blocked_count_nonnegative"),
        Index("ix_download_stats_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_file_id: Mapped[int] = mapped_column(
        ForeignKey("release_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    successful_download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    blocked_download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    release_file: Mapped[ReleaseFile] = relationship(back_populates="download_stats")


if TYPE_CHECKING:
    from app.models.release_file import ReleaseFile
