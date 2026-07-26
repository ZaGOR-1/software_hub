"""Application service coordinating upload, validation, quarantine and metadata."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import UploadFile

from app.core.config import AppSettings
from app.core.exceptions import (
    ApplicationError,
    EntityNotFound,
    StorageError,
    ValidationError,
)
from app.database.session import Database
from app.models.enums import (
    Architecture,
    FileStatus,
    PackageType,
    ScannerStatus,
    SignatureStatus,
    Visibility,
)
from app.models.release_file import ReleaseFile
from app.repositories.release_file_repository import ReleaseFileRepository
from app.repositories.release_repository import ReleaseRepository
from app.services.audit_service import (
    AuditAction,
    AuditContext,
    AuditResult,
    append_audit_event,
    append_context_audit_event,
)
from app.services.normalization import normalize_http_url, normalize_optional_text
from app.storage.manager import StorageManager
from app.storage.move import atomic_move
from app.storage.scanner import FileScanner, ScanResult
from app.storage.signatures import SignatureAssessment, SignatureValidation
from app.storage.upload import StreamedUpload, stream_upload_to_temporary
from app.storage.validation import normalize_display_filename, validate_file_signature

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadMetadata:
    """Validated administrator-supplied metadata independent of the file body."""

    display_filename: str | None
    architecture: Architecture
    package_type: PackageType
    platform: str
    edition: str | None = None
    visibility: Visibility = Visibility.PRIVATE
    source_url: str | None = None
    admin_note: str | None = None


class UploadService:
    """Coordinate a failure-compensated upload without long DB transactions."""

    def __init__(self, database: Database, settings: AppSettings) -> None:
        self.database = database
        self.settings = settings

    async def upload_release_file(
        self,
        *,
        release_id: int,
        upload: UploadFile,
        metadata: UploadMetadata,
        storage: StorageManager,
        scanner: FileScanner,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Stream, validate, quarantine, scan and persist one release file."""

        self._require_release(release_id)
        streamed: StreamedUpload | None = None
        quarantine_path: Path | None = None
        try:
            streamed = await stream_upload_to_temporary(
                upload,
                settings=self.settings,
                paths=storage.paths,
            )
            signature = validate_file_signature(
                streamed.path_plan.original.extension,
                streamed.signature_sample,
            )
            move_result = atomic_move(
                source_root=storage.paths.temporary,
                source_relative_path=streamed.path_plan.temporary_relative_path,
                destination_root=storage.paths.quarantine,
                destination_relative_path=streamed.path_plan.quarantine_relative_path,
            )
            quarantine_path = move_result.destination
            scan_result = await asyncio.to_thread(scanner.scan, quarantine_path)
            release_file = self._persist_metadata(
                release_id=release_id,
                streamed=streamed,
                signature=signature,
                scan_result=scan_result,
                metadata=metadata,
                audit=audit,
            )
        except ApplicationError as exc:
            self._cleanup_paths(streamed, quarantine_path)
            self._record_failure(release_id, audit, type(exc).__name__)
            raise
        except Exception as exc:
            self._cleanup_paths(streamed, quarantine_path)
            self._record_failure(release_id, audit, type(exc).__name__)
            logger.exception(
                "release_file_upload_failed",
                extra={"release_id": release_id, "exception_type": type(exc).__name__},
            )
            raise StorageError("The upload could not be completed safely.") from exc
        finally:
            try:
                await upload.close()
            except OSError:
                logger.warning("framework_upload_close_failed")
        return release_file

    def _require_release(self, release_id: int) -> None:
        with self.database.session() as session:
            if ReleaseRepository(session).get(release_id) is None:
                raise EntityNotFound("Release not found.")

    def _persist_metadata(
        self,
        *,
        release_id: int,
        streamed: StreamedUpload,
        signature: SignatureValidation,
        scan_result: ScanResult,
        metadata: UploadMetadata,
        audit: AuditContext | None,
    ) -> ReleaseFile:
        original = streamed.path_plan.original
        try:
            display_filename = normalize_display_filename(
                metadata.display_filename,
                original=original,
                allowed_extensions=self.settings.allowed_extensions,
            )
            platform = _required_text(
                metadata.platform,
                max_length=100,
                field_name="Platform",
            )
            edition = normalize_optional_text(metadata.edition, max_length=180)
            source_url = normalize_http_url(metadata.source_url)
            admin_note = normalize_optional_text(metadata.admin_note, max_length=4_000)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        detected_mime = (
            signature.detected.mime_type
            if signature.detected is not None
            else "application/octet-stream"
        )
        status = _initial_status(signature, scan_result.status)
        scanner_details = normalize_optional_text(scan_result.details, max_length=500)

        try:
            with self.database.transaction() as session:
                release = ReleaseRepository(session).get_with_graph(release_id, for_update=True)
                if release is None:
                    raise EntityNotFound("Release not found.")
                repository = ReleaseFileRepository(session)
                duplicates = repository.find_by_sha256(streamed.sha256)
                release_file = repository.add(
                    ReleaseFile(
                        release_id=release_id,
                        original_filename=original.value,
                        display_filename=display_filename,
                        storage_filename=streamed.path_plan.storage_filename,
                        relative_storage_path=(
                            streamed.path_plan.quarantine_relative_path.as_posix()
                        ),
                        file_extension=original.extension,
                        detected_mime_type=detected_mime,
                        file_size_bytes=streamed.size_bytes,
                        sha256=streamed.sha256,
                        architecture=metadata.architecture,
                        package_type=metadata.package_type,
                        platform=platform,
                        edition=edition,
                        status=status,
                        visibility=metadata.visibility,
                        source_url=source_url,
                        signature_status=SignatureStatus.NOT_CHECKED,
                        scanner_status=scan_result.status,
                        scanner_details=scanner_details,
                        admin_note=admin_note,
                    )
                )
                append_context_audit_event(
                    session,
                    context=audit,
                    action=AuditAction.FILE_UPLOADED,
                    entity_type="release_file",
                    entity_id=release_file.id,
                    metadata={
                        "release_id": release_id,
                        "file_size_bytes": streamed.size_bytes,
                        "file_extension": original.extension,
                        "signature_assessment": signature.assessment.value,
                        "scanner_status": scan_result.status.value,
                        "duplicate_count": len(duplicates),
                        "initial_status": status.value,
                    },
                )
                return release_file
        except SQLAlchemyError as exc:
            raise StorageError("File metadata could not be saved.") from exc

    def _record_failure(
        self,
        release_id: int,
        audit: AuditContext | None,
        reason: str,
    ) -> None:
        if audit is None:
            return
        try:
            with self.database.transaction() as session:
                append_audit_event(
                    session,
                    action=AuditAction.FILE_UPLOAD_FAILED,
                    result=AuditResult.FAILURE,
                    user_id=audit.user_id,
                    entity_type="release",
                    entity_id=str(release_id),
                    request_id=audit.request_id,
                    ip_hash=audit.ip_hash,
                    metadata={"reason": reason},
                )
        except Exception as exc:
            logger.exception(
                "file_upload_failure_audit_failed",
                extra={"release_id": release_id, "exception_type": type(exc).__name__},
            )

    @staticmethod
    def _cleanup_paths(streamed: StreamedUpload | None, quarantine_path: Path | None) -> None:
        candidates: list[Path] = []
        if streamed is not None:
            candidates.append(streamed.path_plan.temporary_path)
        if quarantine_path is not None:
            candidates.append(quarantine_path)
        for path in candidates:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("upload_compensation_cleanup_failed")


def _initial_status(
    signature: SignatureValidation,
    scanner_status: ScannerStatus,
) -> FileStatus:
    if scanner_status is ScannerStatus.INFECTED:
        return FileStatus.REJECTED
    if signature.assessment is not SignatureAssessment.MATCH:
        return FileStatus.QUARANTINE
    if scanner_status is ScannerStatus.ERROR:
        return FileStatus.QUARANTINE
    return FileStatus.READY


def _required_text(value: str, *, max_length: int, field_name: str) -> str:
    normalized = normalize_optional_text(value, max_length=max_length)
    if normalized is None:
        raise ValueError(f"{field_name} is required.")
    return normalized
