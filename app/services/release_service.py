"""Software release application service and current-version orchestration."""

from datetime import date

from app.core.exceptions import (
    EntityConflict,
    EntityNotFound,
    InvalidStateTransition,
    ValidationError,
)
from app.core.time import utc_now
from app.database.session import Database
from app.models.enums import ReleaseChannel, ReleaseStatus
from app.models.release import Release
from app.repositories.release_repository import ReleaseRepository
from app.repositories.software_repository import SoftwareRepository
from app.schemas.pagination import Page, Pagination
from app.services.audit_service import (
    AuditAction,
    AuditContext,
    append_context_audit_event,
)
from app.services.normalization import normalize_optional_text
from app.services.policies import apply_release_transition, ensure_current_stable_candidate


class ReleaseService:
    """Coordinate release creation and lifecycle changes in short transactions."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _normalize_fields(
        *,
        version: str,
        changelog: str | None,
    ) -> tuple[str, str | None]:
        normalized_version = " ".join(version.split())
        if not normalized_version or len(normalized_version) > 100:
            raise ValidationError("Version must contain 1 to 100 characters.")
        try:
            normalized_changelog = normalize_optional_text(changelog, max_length=20_000)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return normalized_version, normalized_changelog

    def create(
        self,
        *,
        software_id: int,
        version: str,
        release_channel: ReleaseChannel = ReleaseChannel.STABLE,
        release_date: date | None = None,
        changelog: str | None = None,
        audit: AuditContext | None = None,
    ) -> Release:
        """Create a draft release under an existing software entry."""

        normalized_version, normalized_changelog = self._normalize_fields(
            version=version,
            changelog=changelog,
        )
        with self.database.transaction() as session:
            software = SoftwareRepository(session).get(software_id)
            if software is None:
                raise EntityNotFound("Software not found.")
            repository = ReleaseRepository(session)
            duplicate = repository.get_by_identity(
                software_id,
                normalized_version,
                release_channel,
            )
            if duplicate is not None:
                raise EntityConflict("This version and release channel already exist.")
            release = repository.add(
                Release(
                    software=software,
                    version=normalized_version,
                    release_channel=release_channel,
                    release_date=release_date,
                    changelog=normalized_changelog,
                    status=ReleaseStatus.DRAFT,
                )
            )
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.RELEASE_CREATED,
                entity_type="release",
                entity_id=release.id,
                metadata={"software_id": software_id, "version": release.version},
            )
            return release

    def get(self, release_id: int) -> Release:
        """Return one release with its parent and files."""

        with self.database.session() as session:
            release = ReleaseRepository(session).get_with_graph(release_id)
            if release is None:
                raise EntityNotFound("Release not found.")
            return release

    def list_for_software(
        self,
        software_id: int,
        pagination: Pagination,
    ) -> Page[Release]:
        """Return one release page for an existing software entry."""

        with self.database.session() as session:
            if SoftwareRepository(session).get(software_id) is None:
                raise EntityNotFound("Software not found.")
            return ReleaseRepository(session).list_for_software(software_id, pagination)

    def update(
        self,
        release_id: int,
        *,
        version: str,
        release_channel: ReleaseChannel,
        release_date: date | None,
        changelog: str | None,
        audit: AuditContext | None = None,
    ) -> Release:
        """Replace editable release metadata while preserving identity constraints."""

        normalized_version, normalized_changelog = self._normalize_fields(
            version=version,
            changelog=changelog,
        )
        with self.database.transaction() as session:
            repository = ReleaseRepository(session)
            release = repository.get_with_graph(release_id, for_update=True)
            if release is None:
                raise EntityNotFound("Release not found.")
            if release.is_current and release_channel is not ReleaseChannel.STABLE:
                raise InvalidStateTransition(
                    "A current stable release must be unset before changing its channel."
                )
            duplicate = repository.get_by_identity(
                release.software_id,
                normalized_version,
                release_channel,
            )
            if duplicate is not None and duplicate.id != release.id:
                raise EntityConflict("This version and release channel already exist.")
            release.version = normalized_version
            release.release_channel = release_channel
            release.release_date = release_date
            release.changelog = normalized_changelog
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.RELEASE_UPDATED,
                entity_type="release",
                entity_id=release.id,
                metadata={"software_id": release.software_id, "version": release.version},
            )
            return release

    def transition_status(
        self,
        release_id: int,
        target: ReleaseStatus,
        *,
        audit: AuditContext | None = None,
    ) -> Release:
        """Apply one validated release transition atomically."""

        with self.database.transaction() as session:
            repository = ReleaseRepository(session)
            release = repository.get_with_graph(release_id, for_update=True)
            if release is None:
                raise EntityNotFound("Release not found.")
            previous = release.status
            apply_release_transition(release, target, now=utc_now())
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.RELEASE_STATUS_CHANGED,
                entity_type="release",
                entity_id=release.id,
                metadata={"from": previous.value, "to": target.value},
            )
            return release

    def set_current_stable(
        self,
        release_id: int,
        *,
        audit: AuditContext | None = None,
    ) -> Release:
        """Atomically replace the current stable release for one software entry."""

        with self.database.transaction() as session:
            repository = ReleaseRepository(session)
            release = repository.get_with_graph(release_id, for_update=True)
            if release is None:
                raise EntityNotFound("Release not found.")
            ensure_current_stable_candidate(release)
            cleared = repository.clear_current_stable(
                release.software_id,
                except_release_id=release.id,
            )
            release.is_current = True
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.RELEASE_CURRENT_CHANGED,
                entity_type="release",
                entity_id=release.id,
                metadata={"software_id": release.software_id, "cleared_count": cleared},
            )
            return release

    def clear_current(
        self,
        release_id: int,
        *,
        audit: AuditContext | None = None,
    ) -> Release:
        """Remove a current marker without changing release status."""

        with self.database.transaction() as session:
            repository = ReleaseRepository(session)
            release = repository.get_with_graph(release_id, for_update=True)
            if release is None:
                raise EntityNotFound("Release not found.")
            release.is_current = False
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.RELEASE_CURRENT_CHANGED,
                entity_type="release",
                entity_id=release.id,
                metadata={"software_id": release.software_id, "current": False},
            )
            return release
