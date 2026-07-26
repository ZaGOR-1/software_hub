"""Process-level storage owner and FastAPI dependency."""

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import AppSettings
from app.storage.cleanup import CleanupReport, cleanup_temporary_files
from app.storage.disk import DiskSpace, ensure_free_space
from app.storage.paths import StoragePaths, ensure_private_directory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StorageManager:
    """Validate, own and expose the private filesystem layout."""

    paths: StoragePaths
    minimum_free_bytes: int
    temporary_file_max_age_seconds: int
    initialized: bool = False

    @classmethod
    def from_settings(cls, settings: AppSettings) -> StorageManager:
        return cls(
            paths=StoragePaths.from_settings(settings),
            minimum_free_bytes=settings.storage_min_free_bytes,
            temporary_file_max_age_seconds=settings.temporary_file_max_age_seconds,
        )

    def initialize(self) -> DiskSpace:
        """Create, permission-harden and probe every required directory."""

        for directory in self.paths.required_directories():
            ensure_private_directory(directory)
        space = ensure_free_space(
            self.paths.root,
            required_bytes=0,
            reserve_bytes=self.minimum_free_bytes,
        )
        self.initialized = True
        logger.info(
            "storage_initialized",
            extra={
                "managed_directory_count": len(self.paths.required_directories()),
                "free_bytes": space.free,
                "minimum_free_bytes": self.minimum_free_bytes,
            },
        )
        return space

    def cleanup_temporary(self, *, dry_run: bool = True) -> CleanupReport:
        """Clean only stale app-generated temporary upload files."""

        report = cleanup_temporary_files(
            self.paths.temporary,
            max_age_seconds=self.temporary_file_max_age_seconds,
            dry_run=dry_run,
        )
        logger.info(
            "temporary_storage_cleanup",
            extra={
                "dry_run": dry_run,
                "examined": report.examined,
                "eligible": report.eligible,
                "deleted": report.deleted,
                "reclaimed_bytes": report.reclaimed_bytes,
                "errors": report.errors,
            },
        )
        return report


def get_storage_manager(request: Request) -> StorageManager:
    """Resolve the initialized process-level storage manager."""

    manager = getattr(request.app.state, "storage", None)
    if not isinstance(manager, StorageManager) or not manager.initialized:
        raise RuntimeError("Storage infrastructure is not initialized.")
    return manager


StorageDependency = Annotated[StorageManager, Depends(get_storage_manager)]
