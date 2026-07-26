"""Read-only storage reconciliation and explicitly destructive maintenance actions."""

from __future__ import annotations

import logging
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from sqlalchemy import select

from app.core.exceptions import StorageError
from app.database.session import Database
from app.models.enums import FileStatus
from app.models.release_file import ReleaseFile
from app.services.audit_service import AuditAction, AuditResult, append_audit_event
from app.storage.hashing import sha256_file
from app.storage.lifecycle import (
    StorageArea,
    StoredFile,
    inspect_stored_files,
    stage_for_permanent_deletion,
    unlink_staged_deletion,
)
from app.storage.manager import StorageManager
from app.storage.paths import safe_resolve

logger = logging.getLogger(__name__)


class ReconciliationIssueKind(StrEnum):
    """Stable issue identifiers suitable for CLI and operations documentation."""

    METADATA_WITHOUT_FILE = "metadata_without_file"
    DUPLICATE_STORAGE_LOCATION = "duplicate_storage_location"
    UNEXPECTED_STORAGE_AREA = "unexpected_storage_area"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    ORPHAN_FILE = "orphan_file"
    UNSAFE_STORAGE_ENTRY = "unsafe_storage_entry"


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    """One bounded mismatch without an absolute filesystem path."""

    kind: ReconciliationIssueKind
    relative_path: str
    file_id: int | None = None
    storage_area: StorageArea | None = None
    expected: str | int | None = None
    actual: str | int | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Complete read-only reconciliation summary."""

    metadata_count: int
    physical_file_count: int
    verified_count: int
    issues: tuple[ReconciliationIssue, ...]

    @property
    def orphan_count(self) -> int:
        return sum(issue.kind is ReconciliationIssueKind.ORPHAN_FILE for issue in self.issues)

    @property
    def mismatch_count(self) -> int:
        return len(self.issues) - self.orphan_count

    @property
    def healthy(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class ChecksumChange:
    """One metadata checksum/size change discovered from physical content."""

    file_id: int
    relative_path: str
    old_sha256: str
    new_sha256: str
    old_size_bytes: int
    new_size_bytes: int
    published: bool


@dataclass(frozen=True, slots=True)
class ChecksumRecalculationReport:
    """Dry-run or applied checksum recalculation result."""

    examined: int
    changes: tuple[ChecksumChange, ...]
    updated_count: int
    skipped_published_count: int
    errors: int
    dry_run: bool


@dataclass(frozen=True, slots=True)
class OrphanCleanupReport:
    """Dry-run or explicit deletion result for unreferenced physical files."""

    discovered: tuple[ReconciliationIssue, ...]
    deleted_count: int
    errors: int
    dry_run: bool


@dataclass(frozen=True, slots=True)
class _FileMetadata:
    file_id: int
    relative_path: str
    sha256: str
    size_bytes: int
    status: FileStatus


class ReconciliationService:
    """Compare SQLite metadata with private storage without trusting either side."""

    def __init__(self, database: Database, storage: StorageManager) -> None:
        self.database = database
        self.storage = storage

    def verify_storage(self, *, verify_checksums: bool = True) -> ReconciliationReport:
        """Report metadata/file mismatches and orphan files without modifying state."""

        metadata = self._metadata_snapshot()
        issues: list[ReconciliationIssue] = []
        known_paths = {item.relative_path for item in metadata}
        physical_count = 0
        verified_count = 0

        for item in metadata:
            try:
                matches = inspect_stored_files(self.storage.paths, item.relative_path)
            except StorageError:
                issues.append(
                    ReconciliationIssue(
                        kind=ReconciliationIssueKind.UNSAFE_STORAGE_ENTRY,
                        relative_path=item.relative_path,
                        file_id=item.file_id,
                    )
                )
                continue
            physical_count += len(matches)
            if not matches:
                issues.append(
                    ReconciliationIssue(
                        kind=ReconciliationIssueKind.METADATA_WITHOUT_FILE,
                        relative_path=item.relative_path,
                        file_id=item.file_id,
                    )
                )
                continue
            if len(matches) > 1:
                issues.append(
                    ReconciliationIssue(
                        kind=ReconciliationIssueKind.DUPLICATE_STORAGE_LOCATION,
                        relative_path=item.relative_path,
                        file_id=item.file_id,
                        actual=len(matches),
                        expected=1,
                    )
                )
                continue
            stored = matches[0]
            if not self._area_allowed(item.status, stored.area):
                issues.append(
                    ReconciliationIssue(
                        kind=ReconciliationIssueKind.UNEXPECTED_STORAGE_AREA,
                        relative_path=item.relative_path,
                        file_id=item.file_id,
                        storage_area=stored.area,
                        expected=self._expected_area_label(item.status),
                        actual=stored.area.value,
                    )
                )
            if stored.size_bytes != item.size_bytes:
                issues.append(
                    ReconciliationIssue(
                        kind=ReconciliationIssueKind.SIZE_MISMATCH,
                        relative_path=item.relative_path,
                        file_id=item.file_id,
                        storage_area=stored.area,
                        expected=item.size_bytes,
                        actual=stored.size_bytes,
                    )
                )
            checksum_matches = True
            if verify_checksums:
                digest, size = sha256_file(stored.path)
                if size != item.size_bytes or digest != item.sha256:
                    checksum_matches = False
                    issues.append(
                        ReconciliationIssue(
                            kind=ReconciliationIssueKind.CHECKSUM_MISMATCH,
                            relative_path=item.relative_path,
                            file_id=item.file_id,
                            storage_area=stored.area,
                            expected=item.sha256,
                            actual=digest,
                        )
                    )
            if stored.size_bytes == item.size_bytes and checksum_matches:
                verified_count += 1

        orphan_issues = self._orphan_issues(known_paths)
        physical_count += len(orphan_issues)
        issues.extend(orphan_issues)
        return ReconciliationReport(
            metadata_count=len(metadata),
            physical_file_count=physical_count,
            verified_count=verified_count,
            issues=tuple(sorted(issues, key=self._issue_sort_key)),
        )

    def recalculate_checksums(
        self,
        *,
        dry_run: bool = True,
        include_published: bool = False,
    ) -> ChecksumRecalculationReport:
        """Recalculate metadata only after explicit apply; published files are protected."""

        metadata = self._metadata_snapshot()
        changes: list[ChecksumChange] = []
        skipped_published = 0
        errors = 0
        physical_state: dict[int, tuple[str, int, int]] = {}
        for item in metadata:
            try:
                matches = inspect_stored_files(self.storage.paths, item.relative_path)
                if len(matches) != 1:
                    errors += 1
                    continue
                stored = matches[0]
                digest, size = sha256_file(stored.path)
                metadata_stat = stored.path.lstat()
            except OSError, StorageError:
                errors += 1
                continue
            if digest == item.sha256 and size == item.size_bytes:
                continue
            published = item.status is FileStatus.PUBLISHED
            if published and not include_published:
                skipped_published += 1
                continue
            changes.append(
                ChecksumChange(
                    file_id=item.file_id,
                    relative_path=item.relative_path,
                    old_sha256=item.sha256,
                    new_sha256=digest,
                    old_size_bytes=item.size_bytes,
                    new_size_bytes=size,
                    published=published,
                )
            )
            physical_state[item.file_id] = (digest, size, metadata_stat.st_mtime_ns)

        updated = 0
        if not dry_run and changes:
            with self.database.transaction() as session:
                for change in changes:
                    entity = session.get(ReleaseFile, change.file_id)
                    if entity is None:
                        errors += 1
                        continue
                    try:
                        matches = inspect_stored_files(
                            self.storage.paths,
                            entity.relative_storage_path,
                        )
                        if len(matches) != 1:
                            errors += 1
                            continue
                        stored = matches[0]
                        expected_digest, expected_size, expected_mtime = physical_state[
                            change.file_id
                        ]
                        current_stat = stored.path.lstat()
                        digest, size = sha256_file(stored.path)
                    except OSError, StorageError:
                        errors += 1
                        continue
                    if (
                        digest != expected_digest
                        or size != expected_size
                        or current_stat.st_mtime_ns != expected_mtime
                    ):
                        errors += 1
                        continue
                    entity.sha256 = digest
                    entity.file_size_bytes = size
                    append_audit_event(
                        session,
                        action=AuditAction.FILE_CHECKSUM_RECALCULATED,
                        result=AuditResult.SUCCESS,
                        entity_type="release_file",
                        entity_id=str(entity.id),
                        request_id="cli",
                        metadata={
                            "changed": True,
                            "file_size_bytes": size,
                            "storage_area": stored.area.value,
                        },
                    )
                    updated += 1
        return ChecksumRecalculationReport(
            examined=len(metadata),
            changes=tuple(changes),
            updated_count=updated,
            skipped_published_count=skipped_published,
            errors=errors,
            dry_run=dry_run,
        )

    def cleanup_orphans(
        self,
        *,
        dry_run: bool = True,
    ) -> OrphanCleanupReport:
        """Delete only unreferenced regular files after an explicit destructive request."""

        known_paths = {item.relative_path for item in self._metadata_snapshot()}
        orphans = self._orphan_issues(known_paths)
        deleted = 0
        errors = 0
        if not dry_run:
            for issue in orphans:
                if issue.storage_area is None:
                    errors += 1
                    continue
                root = self._root_for_area(issue.storage_area)
                relative = PurePosixPath(issue.relative_path)
                try:
                    path = safe_resolve(
                        root,
                        relative,
                        require_exists=True,
                        reject_symlinks=True,
                    )
                    metadata = path.lstat()
                    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                        errors += 1
                        continue
                    stored = StoredFile(
                        area=issue.storage_area,
                        root=root,
                        relative_path=relative,
                        path=path,
                        size_bytes=metadata.st_size,
                    )
                    staged = stage_for_permanent_deletion(self.storage.paths, stored)
                    unlink_staged_deletion(self.storage.paths, staged)
                    deleted += 1
                except OSError, StorageError:
                    errors += 1
        return OrphanCleanupReport(
            discovered=orphans,
            deleted_count=deleted,
            errors=errors,
            dry_run=dry_run,
        )

    def _metadata_snapshot(self) -> tuple[_FileMetadata, ...]:
        with self.database.session() as session:
            rows = session.execute(
                select(
                    ReleaseFile.id,
                    ReleaseFile.relative_storage_path,
                    ReleaseFile.sha256,
                    ReleaseFile.file_size_bytes,
                    ReleaseFile.status,
                ).order_by(ReleaseFile.id)
            ).all()
        return tuple(
            _FileMetadata(
                file_id=row.id,
                relative_path=row.relative_storage_path,
                sha256=row.sha256,
                size_bytes=row.file_size_bytes,
                status=row.status,
            )
            for row in rows
        )

    def _orphan_issues(self, known_paths: set[str]) -> tuple[ReconciliationIssue, ...]:
        issues: list[ReconciliationIssue] = []
        for area, root in (
            (StorageArea.QUARANTINE, self.storage.paths.quarantine),
            (StorageArea.SOFTWARE, self.storage.paths.software),
        ):
            if root.is_symlink() or not root.is_dir():
                issues.append(
                    ReconciliationIssue(
                        kind=ReconciliationIssueKind.UNSAFE_STORAGE_ENTRY,
                        relative_path=".",
                        storage_area=area,
                    )
                )
                continue
            for current, directory_names, file_names in root.walk(follow_symlinks=False):
                unsafe_directories = [
                    name for name in directory_names if (current / name).is_symlink()
                ]
                issues.extend(
                    [
                        ReconciliationIssue(
                            kind=ReconciliationIssueKind.UNSAFE_STORAGE_ENTRY,
                            relative_path=(current / name).relative_to(root).as_posix(),
                            storage_area=area,
                        )
                        for name in unsafe_directories
                    ]
                )
                directory_names[:] = [
                    name for name in directory_names if name not in unsafe_directories
                ]
                for name in file_names:
                    path = current / name
                    relative = path.relative_to(root).as_posix()
                    try:
                        metadata = path.lstat()
                    except OSError:
                        issues.append(
                            ReconciliationIssue(
                                kind=ReconciliationIssueKind.UNSAFE_STORAGE_ENTRY,
                                relative_path=relative,
                                storage_area=area,
                            )
                        )
                        continue
                    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                        issues.append(
                            ReconciliationIssue(
                                kind=ReconciliationIssueKind.UNSAFE_STORAGE_ENTRY,
                                relative_path=relative,
                                storage_area=area,
                            )
                        )
                    elif relative not in known_paths:
                        issues.append(
                            ReconciliationIssue(
                                kind=ReconciliationIssueKind.ORPHAN_FILE,
                                relative_path=relative,
                                storage_area=area,
                                actual=metadata.st_size,
                            )
                        )
        return tuple(sorted(issues, key=self._issue_sort_key))

    def _root_for_area(self, area: StorageArea) -> Path:
        if area is StorageArea.QUARANTINE:
            return self.storage.paths.quarantine
        return self.storage.paths.software

    @staticmethod
    def _area_allowed(status: FileStatus, area: StorageArea) -> bool:
        if status is FileStatus.PUBLISHED:
            return area is StorageArea.SOFTWARE
        if status in {FileStatus.QUARANTINE, FileStatus.READY, FileStatus.REJECTED}:
            return area is StorageArea.QUARANTINE
        return area in {StorageArea.QUARANTINE, StorageArea.SOFTWARE}

    @staticmethod
    def _expected_area_label(status: FileStatus) -> str:
        if status is FileStatus.PUBLISHED:
            return StorageArea.SOFTWARE.value
        if status in {FileStatus.QUARANTINE, FileStatus.READY, FileStatus.REJECTED}:
            return StorageArea.QUARANTINE.value
        return "quarantine_or_software"

    @staticmethod
    def _issue_sort_key(issue: ReconciliationIssue) -> tuple[str, str, int]:
        return (issue.kind.value, issue.relative_path, issue.file_id or 0)
