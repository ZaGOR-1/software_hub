"""Release-file metadata, integrity and physical lifecycle application service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.exceptions import (
    ApplicationError,
    EntityNotFound,
    FileValidationError,
    InvalidStateTransition,
    StorageError,
    ValidationError,
)
from app.core.time import utc_now
from app.database.session import Database
from app.models.enums import (
    FileStatus,
    ReleaseStatus,
    ScannerStatus,
    SoftwareStatus,
    Visibility,
)
from app.models.release_file import ReleaseFile
from app.repositories.release_file_repository import ReleaseFileRepository
from app.schemas.pagination import Page, Pagination
from app.services.audit_service import AuditAction, AuditContext, append_context_audit_event
from app.services.policies import apply_file_transition
from app.storage.hashing import sha256_file
from app.storage.lifecycle import (
    StorageArea,
    StoredFile,
    inspect_stored_files,
    locate_stored_file,
    restore_staged_deletion,
    stage_for_permanent_deletion,
    unlink_staged_deletion,
)
from app.storage.manager import StorageManager
from app.storage.move import atomic_move
from app.storage.signatures import SignatureAssessment, assess_stored_signature

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FileStorageState:
    """Safe storage information displayed in the private admin interface."""

    exists: bool
    area: StorageArea | None
    size_bytes: int | None
    size_matches: bool


@dataclass(frozen=True, slots=True)
class FileDeletionResult:
    """Result of metadata-only or physical release-file deletion."""

    file_id: int
    release_id: int
    physical_file_preserved: bool
    storage_area: StorageArea | None


class FileService:
    """Coordinate release-file metadata and private filesystem lifecycle actions."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, file_id: int) -> ReleaseFile:
        """Return one file with release and software metadata."""

        with self.database.session() as session:
            release_file = ReleaseFileRepository(session).get_with_graph(file_id)
            if release_file is None:
                raise EntityNotFound("Release file not found.")
            return release_file

    def list_for_release(
        self,
        release_id: int,
        pagination: Pagination,
    ) -> Page[ReleaseFile]:
        """Return one release-file page."""

        with self.database.session() as session:
            return ReleaseFileRepository(session).list_for_release(release_id, pagination)

    def find_duplicates(
        self,
        sha256: str,
        *,
        exclude_file_id: int | None = None,
    ) -> list[ReleaseFile]:
        """Return metadata records sharing one validated SHA-256 digest."""

        normalized = sha256.strip().casefold()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValidationError("SHA-256 must be exactly 64 hexadecimal characters.")
        with self.database.session() as session:
            return ReleaseFileRepository(session).find_by_sha256(
                normalized,
                exclude_file_id=exclude_file_id,
            )

    def storage_state(self, file_id: int, storage: StorageManager) -> FileStorageState:
        """Inspect physical presence without exposing an absolute path."""

        release_file = self.get(file_id)
        matches = inspect_stored_files(storage.paths, release_file.relative_storage_path)
        if not matches:
            return FileStorageState(False, None, None, False)
        if len(matches) > 1:
            raise StorageError("The physical file exists in multiple storage locations.")
        stored = matches[0]
        return FileStorageState(
            exists=True,
            area=stored.area,
            size_bytes=stored.size_bytes,
            size_matches=stored.size_bytes == release_file.file_size_bytes,
        )

    def verify_integrity(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Recalculate size and SHA-256 before any trust-sensitive action."""

        release_file = self.get(file_id)
        stored = self._verified_physical_file(release_file, storage, verify_hash=True)
        with self.database.transaction() as session:
            current = ReleaseFileRepository(session).get_with_graph(file_id, for_update=True)
            if current is None:
                raise EntityNotFound("Release file not found.")
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.FILE_VERIFIED,
                entity_type="release_file",
                entity_id=current.id,
                metadata={"storage_area": stored.area.value},
            )
        return release_file

    def review_status(
        self,
        file_id: int,
        target: FileStatus,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Apply a manual quarantine review decision without publishing content."""

        if target not in {FileStatus.READY, FileStatus.REJECTED, FileStatus.QUARANTINE}:
            raise InvalidStateTransition("This status is not a manual review decision.")
        release_file = self.get(file_id)
        stored = self._verified_physical_file(release_file, storage)
        if stored.area is not StorageArea.QUARANTINE:
            raise StorageError("Files under review must remain in quarantine storage.")
        with self.database.transaction() as session:
            repository = ReleaseFileRepository(session)
            current = repository.get_with_graph(file_id, for_update=True)
            if current is None:
                raise EntityNotFound("Release file not found.")
            previous = current.status
            apply_file_transition(current, target, now=utc_now())
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.FILE_REVIEWED,
                entity_type="release_file",
                entity_id=current.id,
                metadata={"from": previous.value, "to": target.value},
            )
            session.flush()
        return self.get(file_id)

    def publish(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Verify, atomically move and publish one ready release file."""

        release_file = self.get(file_id)
        self._ensure_publish_ready(release_file)
        stored = self._verified_physical_file(release_file, storage, verify_hash=True)
        if stored.area is not StorageArea.QUARANTINE:
            raise StorageError("A ready file must be located in quarantine before publication.")

        atomic_move(
            source_root=storage.paths.quarantine,
            source_relative_path=stored.relative_path,
            destination_root=storage.paths.software,
            destination_relative_path=stored.relative_path,
        )
        try:
            with self.database.transaction() as session:
                repository = ReleaseFileRepository(session)
                current = repository.get_with_graph(file_id, for_update=True)
                if current is None:
                    raise EntityNotFound("Release file not found.")
                self._ensure_publish_ready(current)
                if current.relative_storage_path != stored.relative_path.as_posix():
                    raise StorageError("File metadata changed during publication.")
                apply_file_transition(current, FileStatus.PUBLISHED, now=utc_now())
                current.relative_storage_path = stored.relative_path.as_posix()
                append_context_audit_event(
                    session,
                    context=audit,
                    action=AuditAction.FILE_PUBLISHED,
                    entity_type="release_file",
                    entity_id=current.id,
                    metadata={
                        "release_id": current.release_id,
                        "storage_area": StorageArea.SOFTWARE.value,
                    },
                )
                session.flush()
        except Exception as exc:
            self._restore_move_after_failure(
                storage,
                source_area=StorageArea.SOFTWARE,
                destination_area=StorageArea.QUARANTINE,
                relative_path=stored.relative_path,
                original_error=exc,
            )
            if isinstance(exc, ApplicationError):
                raise
            raise StorageError("File publication metadata could not be saved.") from exc
        return self.get(file_id)

    def disable(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Disable access without deleting or relocating physical content."""

        return self._transition_with_storage_check(
            file_id,
            FileStatus.DISABLED,
            storage,
            audit=audit,
            action=AuditAction.FILE_DISABLED,
        )

    def archive(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Archive a file while preserving its physical bytes."""

        return self._transition_with_storage_check(
            file_id,
            FileStatus.ARCHIVED,
            storage,
            audit=audit,
            action=AuditAction.FILE_ARCHIVED,
        )

    def restore_ready(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> ReleaseFile:
        """Return disabled or archived content to private ready/quarantine state."""

        release_file = self.get(file_id)
        stored = self._verified_physical_file(release_file, storage)
        moved_from_software = stored.area is StorageArea.SOFTWARE
        if moved_from_software:
            atomic_move(
                source_root=storage.paths.software,
                source_relative_path=stored.relative_path,
                destination_root=storage.paths.quarantine,
                destination_relative_path=stored.relative_path,
            )
        try:
            with self.database.transaction() as session:
                current = ReleaseFileRepository(session).get_with_graph(file_id, for_update=True)
                if current is None:
                    raise EntityNotFound("Release file not found.")
                previous = current.status
                apply_file_transition(current, FileStatus.READY, now=utc_now())
                append_context_audit_event(
                    session,
                    context=audit,
                    action=AuditAction.FILE_RESTORED,
                    entity_type="release_file",
                    entity_id=current.id,
                    metadata={"from": previous.value, "to": FileStatus.READY.value},
                )
                session.flush()
        except Exception as exc:
            if moved_from_software:
                self._restore_move_after_failure(
                    storage,
                    source_area=StorageArea.QUARANTINE,
                    destination_area=StorageArea.SOFTWARE,
                    relative_path=stored.relative_path,
                    original_error=exc,
                )
            if isinstance(exc, ApplicationError):
                raise
            raise StorageError("File restore metadata could not be saved.") from exc
        return self.get(file_id)

    def delete_metadata(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> FileDeletionResult:
        """Delete only metadata, intentionally preserving any physical file as an orphan."""

        release_file = self.get(file_id)
        self._ensure_deletable(release_file)
        matches = inspect_stored_files(storage.paths, release_file.relative_storage_path)
        if len(matches) > 1:
            raise StorageError("The physical file exists in multiple storage locations.")
        stored = matches[0] if matches else None
        with self.database.transaction() as session:
            repository = ReleaseFileRepository(session)
            current = repository.get_with_graph(file_id, for_update=True)
            if current is None:
                raise EntityNotFound("Release file not found.")
            self._ensure_deletable(current)
            release_id = current.release_id
            repository.delete(current)
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.FILE_METADATA_DELETED,
                entity_type="release_file",
                entity_id=file_id,
                metadata={
                    "release_id": release_id,
                    "physical_file_preserved": stored is not None,
                    "storage_area": stored.area.value if stored else None,
                },
            )
        return FileDeletionResult(
            file_id=file_id,
            release_id=release_id,
            physical_file_preserved=stored is not None,
            storage_area=stored.area if stored else None,
        )

    def permanently_delete(
        self,
        file_id: int,
        storage: StorageManager,
        *,
        audit: AuditContext | None = None,
    ) -> FileDeletionResult:
        """Stage bytes, delete metadata atomically, then remove staged content."""

        release_file = self.get(file_id)
        self._ensure_deletable(release_file)
        stored = self._verified_physical_file(release_file, storage)
        staged = stage_for_permanent_deletion(storage.paths, stored)
        try:
            with self.database.transaction() as session:
                repository = ReleaseFileRepository(session)
                current = repository.get_with_graph(file_id, for_update=True)
                if current is None:
                    raise EntityNotFound("Release file not found.")
                self._ensure_deletable(current)
                if current.relative_storage_path != stored.relative_path.as_posix():
                    raise StorageError("File metadata changed during permanent deletion.")
                release_id = current.release_id
                repository.delete(current)
                append_context_audit_event(
                    session,
                    context=audit,
                    action=AuditAction.FILE_PERMANENTLY_DELETED,
                    entity_type="release_file",
                    entity_id=file_id,
                    metadata={
                        "release_id": release_id,
                        "storage_area": stored.area.value,
                        "file_size_bytes": stored.size_bytes,
                    },
                )
        except Exception as exc:
            try:
                restore_staged_deletion(storage.paths, staged)
            except StorageError as restore_error:
                logger.critical(
                    "permanent_delete_compensation_failed",
                    extra={"file_id": file_id, "exception_type": type(restore_error).__name__},
                )
                raise StorageError(
                    "Permanent deletion failed and the physical file could not be restored."
                ) from exc
            if isinstance(exc, ApplicationError):
                raise
            raise StorageError("File metadata could not be permanently deleted.") from exc

        try:
            unlink_staged_deletion(storage.paths, staged)
        except StorageError as exc:
            logger.critical(
                "permanent_delete_staged_cleanup_failed",
                extra={"file_id": file_id},
            )
            raise StorageError(
                "Metadata was removed, but staged file cleanup requires operator attention."
            ) from exc
        return FileDeletionResult(
            file_id=file_id,
            release_id=release_id,
            physical_file_preserved=False,
            storage_area=stored.area,
        )

    def transition_status(self, file_id: int, target: FileStatus) -> ReleaseFile:
        """Apply one metadata-only transition for internal or legacy callers."""

        with self.database.transaction() as session:
            repository = ReleaseFileRepository(session)
            release_file = repository.get_with_graph(file_id, for_update=True)
            if release_file is None:
                raise EntityNotFound("Release file not found.")
            apply_file_transition(release_file, target, now=utc_now())
            session.flush()
            return release_file

    def set_visibility(self, file_id: int, visibility: Visibility) -> ReleaseFile:
        """Change file visibility without changing validation status."""

        with self.database.transaction() as session:
            repository = ReleaseFileRepository(session)
            release_file = repository.get(file_id)
            if release_file is None:
                raise EntityNotFound("Release file not found.")
            release_file.visibility = visibility
            session.flush()
            return release_file

    def _transition_with_storage_check(
        self,
        file_id: int,
        target: FileStatus,
        storage: StorageManager,
        *,
        audit: AuditContext | None,
        action: AuditAction,
    ) -> ReleaseFile:
        release_file = self.get(file_id)
        stored = self._verified_physical_file(release_file, storage)
        with self.database.transaction() as session:
            current = ReleaseFileRepository(session).get_with_graph(file_id, for_update=True)
            if current is None:
                raise EntityNotFound("Release file not found.")
            previous = current.status
            apply_file_transition(current, target, now=utc_now())
            append_context_audit_event(
                session,
                context=audit,
                action=action,
                entity_type="release_file",
                entity_id=current.id,
                metadata={
                    "from": previous.value,
                    "to": target.value,
                    "storage_area": stored.area.value,
                },
            )
            session.flush()
        return self.get(file_id)

    @staticmethod
    def _ensure_publish_ready(release_file: ReleaseFile) -> None:
        if release_file.status is not FileStatus.READY:
            raise InvalidStateTransition("Only a ready file can be published.")
        if (
            assess_stored_signature(
                release_file.file_extension,
                release_file.detected_mime_type,
            )
            is not SignatureAssessment.MATCH
        ):
            raise FileValidationError("The stored file signature is not approved for publication.")
        if release_file.release.status is not ReleaseStatus.PUBLISHED:
            raise InvalidStateTransition("The parent release must be published first.")
        if release_file.release.software.status not in {
            SoftwareStatus.PUBLISHED,
            SoftwareStatus.HIDDEN,
        }:
            raise InvalidStateTransition("The parent software must be published or hidden first.")
        if release_file.scanner_status not in {ScannerStatus.CLEAN, ScannerStatus.UNAVAILABLE}:
            raise InvalidStateTransition(
                "The scanner result must be clean or unavailable before publication."
            )

    @staticmethod
    def _ensure_deletable(release_file: ReleaseFile) -> None:
        if release_file.status is FileStatus.PUBLISHED:
            raise InvalidStateTransition("Disable or archive a published file before deletion.")

    @staticmethod
    def _verified_physical_file(
        release_file: ReleaseFile,
        storage: StorageManager,
        *,
        verify_hash: bool = False,
    ) -> StoredFile:
        stored = locate_stored_file(storage.paths, release_file.relative_storage_path)
        if stored.size_bytes != release_file.file_size_bytes:
            raise FileValidationError("The stored file size no longer matches its metadata.")
        if verify_hash:
            digest, size_bytes = sha256_file(stored.path)
            if size_bytes != release_file.file_size_bytes or digest != release_file.sha256:
                raise FileValidationError(
                    "The stored file checksum no longer matches its metadata."
                )
        return stored

    @staticmethod
    def _restore_move_after_failure(
        storage: StorageManager,
        *,
        source_area: StorageArea,
        destination_area: StorageArea,
        relative_path: str | Path | PurePosixPath,
        original_error: Exception,
    ) -> None:
        roots = {
            StorageArea.QUARANTINE: storage.paths.quarantine,
            StorageArea.SOFTWARE: storage.paths.software,
        }
        try:
            atomic_move(
                source_root=roots[source_area],
                source_relative_path=relative_path,
                destination_root=roots[destination_area],
                destination_relative_path=relative_path,
            )
        except StorageError as restore_error:
            logger.critical(
                "file_lifecycle_compensation_failed",
                extra={"exception_type": type(restore_error).__name__},
            )
            raise StorageError(
                "The file lifecycle action failed and storage compensation was incomplete."
            ) from original_error
