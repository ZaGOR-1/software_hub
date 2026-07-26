"""Downloadable release file model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database.base import Base
from app.database.types import UTCDateTime
from app.models.enums import (
    Architecture,
    FileStatus,
    PackageType,
    ScannerStatus,
    SignatureStatus,
    Visibility,
)
from app.models.mixins import TimestampMixin
from app.models.types import enum_type


class ReleaseFile(TimestampMixin, Base):
    """Validated file metadata; binary content remains outside the database."""

    __tablename__ = "release_files"
    __table_args__ = (
        CheckConstraint("file_size_bytes >= 0", name="file_size_nonnegative"),
        CheckConstraint("download_count >= 0", name="download_count_nonnegative"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        Index("ix_release_files_release_status", "release_id", "status"),
        Index("ix_release_files_status_visibility", "status", "visibility"),
        Index("ix_release_files_sha256", "sha256"),
        Index("ix_release_files_uploaded_at", "uploaded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        default=uuid4,
        unique=True,
        index=True,
    )
    release_id: Mapped[int] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    display_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    relative_storage_path: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    architecture: Mapped[Architecture] = mapped_column(
        enum_type(Architecture, name="file_architecture"),
        nullable=False,
        default=Architecture.OTHER,
        server_default=Architecture.OTHER.value,
    )
    package_type: Mapped[PackageType] = mapped_column(
        enum_type(PackageType, name="file_package_type"),
        nullable=False,
        default=PackageType.OTHER,
        server_default=PackageType.OTHER.value,
    )
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(180), nullable=True)
    download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    status: Mapped[FileStatus] = mapped_column(
        enum_type(FileStatus, name="file_status"),
        nullable=False,
        default=FileStatus.QUARANTINE,
        server_default=FileStatus.QUARANTINE.value,
        index=True,
    )
    visibility: Mapped[Visibility] = mapped_column(
        enum_type(Visibility, name="file_visibility"),
        nullable=False,
        default=Visibility.PRIVATE,
        server_default=Visibility.PRIVATE.value,
        index=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    signature_status: Mapped[SignatureStatus] = mapped_column(
        enum_type(SignatureStatus, name="signature_status"),
        nullable=False,
        default=SignatureStatus.UNKNOWN,
        server_default=SignatureStatus.UNKNOWN.value,
    )
    scanner_status: Mapped[ScannerStatus] = mapped_column(
        enum_type(ScannerStatus, name="scanner_status"),
        nullable=False,
        default=ScannerStatus.NOT_SCANNED,
        server_default=ScannerStatus.NOT_SCANNED.value,
    )
    scanner_details: Mapped[str | None] = mapped_column(String(500), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    release: Mapped[Release] = relationship(back_populates="files")
    download_stats: Mapped[list[DownloadStat]] = relationship(
        back_populates="release_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


if TYPE_CHECKING:
    from app.models.download_stat import DownloadStat
    from app.models.release import Release
