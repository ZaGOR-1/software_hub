"""Import all domain models so SQLAlchemy metadata is complete."""

from app.models.associations import software_tags
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.download_stat import DownloadStat
from app.models.enums import (
    Architecture,
    FileStatus,
    PackageType,
    ReleaseChannel,
    ReleaseStatus,
    ScannerStatus,
    SignatureStatus,
    SoftwareStatus,
    Visibility,
)
from app.models.release import Release
from app.models.release_file import ReleaseFile
from app.models.session import UserSession
from app.models.software import Software
from app.models.tag import Tag
from app.models.user import User

__all__ = [
    "Architecture",
    "AuditLog",
    "Category",
    "DownloadStat",
    "FileStatus",
    "PackageType",
    "Release",
    "ReleaseChannel",
    "ReleaseFile",
    "ReleaseStatus",
    "ScannerStatus",
    "SignatureStatus",
    "Software",
    "SoftwareStatus",
    "Tag",
    "User",
    "UserSession",
    "Visibility",
    "software_tags",
]
