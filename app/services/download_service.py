"""Authorization, accounting and internal redirect preparation for downloads."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import AppSettings
from app.core.exceptions import EntityNotFound, StorageError
from app.database.session import Database
from app.models.enums import Visibility
from app.repositories.download_stat_repository import DownloadStatRepository
from app.repositories.release_file_repository import ReleaseFileRepository
from app.services.policies import can_download_file
from app.storage.lifecycle import StorageArea, locate_stored_file
from app.storage.manager import StorageManager

logger = logging.getLogger(__name__)
_MEDIA_TYPE_PATTERN = re.compile(r"^[!#$&^_.+\-0-9A-Za-z]+/[!#$&^_.+\-0-9A-Za-z]+$")


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    """Safe headers required for one Nginx-backed file response."""

    internal_redirect_uri: str
    content_disposition: str
    content_type: str
    etag: str
    cache_control: str
    is_private: bool


class DownloadService:
    """Validate the full metadata chain and account an authorized download start."""

    def __init__(
        self,
        database: Database,
        settings: AppSettings,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.clock = clock or _utc_now

    def authorize(
        self,
        *,
        public_uuid: UUID,
        requested_filename: str,
        storage: StorageManager,
        is_admin: bool,
        count_download: bool,
    ) -> DownloadGrant:
        """Return an internal redirect grant or a non-enumerating 404."""

        with self.database.session() as session:
            release_file = ReleaseFileRepository(session).get_by_public_uuid(public_uuid)

        if release_file is None:
            raise EntityNotFound()

        if requested_filename != release_file.display_filename:
            self._record_blocked(release_file.id, reason="filename_mismatch")
            raise EntityNotFound()

        if not can_download_file(release_file, is_admin=is_admin):
            self._record_blocked(release_file.id, reason="authorization_chain")
            raise EntityNotFound()

        try:
            stored_file = locate_stored_file(
                storage.paths,
                release_file.relative_storage_path,
            )
        except StorageError as exc:
            logger.exception(
                "download_storage_lookup_failed",
                extra={
                    "release_file_id": release_file.id,
                    "exception_type": type(exc).__name__,
                },
            )
            raise EntityNotFound() from exc

        if stored_file.area is not StorageArea.SOFTWARE:
            logger.error(
                "download_file_not_in_permanent_storage",
                extra={"release_file_id": release_file.id},
            )
            raise EntityNotFound()
        if stored_file.size_bytes != release_file.file_size_bytes:
            logger.error(
                "download_file_size_mismatch",
                extra={
                    "release_file_id": release_file.id,
                    "metadata_size": release_file.file_size_bytes,
                    "physical_size": stored_file.size_bytes,
                },
            )
            raise EntityNotFound()

        if count_download:
            self._record_authorized_start(release_file.id)

        is_private = release_file.visibility is Visibility.PRIVATE
        return DownloadGrant(
            internal_redirect_uri=_internal_redirect_uri(
                self.settings.internal_download_prefix,
                stored_file.relative_path,
            ),
            content_disposition=build_content_disposition(release_file.display_filename),
            content_type=safe_media_type(release_file.detected_mime_type),
            etag=f'"sha256-{release_file.sha256}"',
            cache_control="private, no-store" if is_private else "no-store",
            is_private=is_private,
        )

    def _record_authorized_start(self, release_file_id: int) -> None:
        day = self.clock().astimezone(UTC).date()
        with self.database.transaction() as session:
            DownloadStatRepository(session).record_authorized_start(release_file_id, day)
        logger.info(
            "download_authorized_start",
            extra={"release_file_id": release_file_id},
        )

    def _record_blocked(self, release_file_id: int, *, reason: str) -> None:
        day = self.clock().astimezone(UTC).date()
        try:
            with self.database.transaction() as session:
                DownloadStatRepository(session).record_blocked(release_file_id, day)
        except SQLAlchemyError as exc:
            logger.exception(
                "download_blocked_accounting_failed",
                extra={
                    "release_file_id": release_file_id,
                    "exception_type": type(exc).__name__,
                },
            )
        logger.warning(
            "download_blocked",
            extra={"release_file_id": release_file_id, "reason": reason},
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def safe_media_type(value: str) -> str:
    """Return one header-safe media type or a conservative binary fallback."""

    candidate = value.strip().casefold()
    if _MEDIA_TYPE_PATTERN.fullmatch(candidate) is None:
        return "application/octet-stream"
    return candidate


def build_content_disposition(filename: str) -> str:
    """Build RFC 6266-compatible attachment metadata with a safe ASCII fallback."""

    extension = PurePosixPath(filename).suffix
    source_stem = filename[: -len(extension)] if extension else filename
    normalized_stem = unicodedata.normalize("NFKD", source_stem)
    ascii_stem = normalized_stem.encode("ascii", "ignore").decode("ascii")
    safe_stem = "".join(
        character if character.isalnum() or character in " ._-" else "_" for character in ascii_stem
    ).strip(" ._")
    fallback = (
        f"{safe_stem}{extension.casefold()}" if safe_stem else f"download{extension.casefold()}"
    )
    if len(fallback) > 150:
        fallback = f"download{extension.casefold()}"
    fallback = fallback.replace('"', "_").replace("\\", "_")
    encoded = quote(filename, safe="", encoding="utf-8", errors="strict")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _internal_redirect_uri(prefix: str, relative_path: PurePosixPath) -> str:
    path = relative_path.as_posix()
    return f"{prefix}{quote(path, safe='/')}"
