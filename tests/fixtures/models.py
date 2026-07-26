"""Small explicit model factories used by integration tests."""

from datetime import date, timedelta

from app.core.time import utc_now
from app.models import (
    Architecture,
    Category,
    DownloadStat,
    FileStatus,
    PackageType,
    Release,
    ReleaseChannel,
    ReleaseFile,
    ReleaseStatus,
    ScannerStatus,
    SignatureStatus,
    Software,
    SoftwareStatus,
    Tag,
    User,
    UserSession,
    Visibility,
)
from sqlalchemy.orm import Session


def make_user(*, username: str = "admin") -> User:
    """Build an unsaved administrator."""

    return User(
        username=username,
        password_hash="$argon2id$test-only-placeholder",
        is_active=True,
        is_superuser=True,
    )


def make_session(user: User, *, token_hash: str = "1" * 64) -> UserSession:
    """Build an unsaved server-side session."""

    now = utc_now()
    return UserSession(
        user=user,
        session_token_hash=token_hash,
        created_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(hours=12),
        csrf_secret_hash="2" * 64,
    )


def make_catalog_graph(session: Session, *, slug: str = "7-zip") -> ReleaseFile:
    """Persist one category/tag/software/release/file/stat graph."""

    category = Category(name="Archivers", slug=f"{slug}-category")
    tag = Tag(name="Utility", slug=f"{slug}-tag")
    software = Software(
        name="7-Zip",
        slug=slug,
        short_description="File archiver",
        category=category,
        tags=[tag],
        status=SoftwareStatus.PUBLISHED,
        visibility=Visibility.PUBLIC,
    )
    release = Release(
        software=software,
        version="26.00",
        release_channel=ReleaseChannel.STABLE,
        release_date=date(2026, 7, 1),
        is_current=True,
        status=ReleaseStatus.PUBLISHED,
    )
    release_file = ReleaseFile(
        release=release,
        original_filename="7z2600-x64.exe",
        display_filename="7-Zip 26.00 x64 Installer.exe",
        storage_filename=f"{slug}-storage.exe",
        relative_storage_path=f"{slug}/26.00/{slug}-storage.exe",
        file_extension=".exe",
        detected_mime_type="application/vnd.microsoft.portable-executable",
        file_size_bytes=1_500_000,
        sha256="a" * 64,
        architecture=Architecture.X64,
        package_type=PackageType.INSTALLER,
        platform="windows",
        status=FileStatus.PUBLISHED,
        visibility=Visibility.PUBLIC,
        signature_status=SignatureStatus.VALID,
        scanner_status=ScannerStatus.CLEAN,
    )
    release_file.download_stats.append(
        DownloadStat(
            date=date(2026, 7, 23),
            download_count=3,
            successful_download_count=3,
            blocked_download_count=0,
        )
    )
    session.add(software)
    session.flush()
    return release_file
