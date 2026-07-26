"""Pure domain policies for lifecycle transitions and public visibility."""

from collections.abc import Mapping, Set
from datetime import datetime
from typing import TypeVar

from app.core.exceptions import InvalidStateTransition
from app.models.enums import (
    FileStatus,
    ReleaseChannel,
    ReleaseStatus,
    ScannerStatus,
    SoftwareStatus,
    Visibility,
)
from app.models.release import Release
from app.models.release_file import ReleaseFile
from app.models.software import Software

SOFTWARE_TRANSITIONS: Mapping[SoftwareStatus, Set[SoftwareStatus]] = {
    SoftwareStatus.DRAFT: {
        SoftwareStatus.PUBLISHED,
        SoftwareStatus.HIDDEN,
        SoftwareStatus.DISABLED,
    },
    SoftwareStatus.PUBLISHED: {
        SoftwareStatus.HIDDEN,
        SoftwareStatus.ARCHIVED,
        SoftwareStatus.DISABLED,
    },
    SoftwareStatus.HIDDEN: {
        SoftwareStatus.DRAFT,
        SoftwareStatus.PUBLISHED,
        SoftwareStatus.ARCHIVED,
        SoftwareStatus.DISABLED,
    },
    SoftwareStatus.ARCHIVED: {
        SoftwareStatus.PUBLISHED,
        SoftwareStatus.HIDDEN,
        SoftwareStatus.DISABLED,
    },
    SoftwareStatus.DISABLED: {SoftwareStatus.DRAFT},
}

RELEASE_TRANSITIONS: Mapping[ReleaseStatus, Set[ReleaseStatus]] = {
    ReleaseStatus.DRAFT: {
        ReleaseStatus.PUBLISHED,
        ReleaseStatus.ARCHIVED,
        ReleaseStatus.DISABLED,
    },
    ReleaseStatus.PUBLISHED: {ReleaseStatus.ARCHIVED, ReleaseStatus.DISABLED},
    ReleaseStatus.ARCHIVED: {ReleaseStatus.PUBLISHED, ReleaseStatus.DISABLED},
    ReleaseStatus.DISABLED: {ReleaseStatus.DRAFT},
}

FILE_TRANSITIONS: Mapping[FileStatus, Set[FileStatus]] = {
    FileStatus.QUARANTINE: {
        FileStatus.READY,
        FileStatus.REJECTED,
        FileStatus.DISABLED,
    },
    FileStatus.READY: {
        FileStatus.PUBLISHED,
        FileStatus.REJECTED,
        FileStatus.DISABLED,
        FileStatus.ARCHIVED,
    },
    FileStatus.PUBLISHED: {FileStatus.DISABLED, FileStatus.ARCHIVED},
    FileStatus.DISABLED: {FileStatus.READY, FileStatus.ARCHIVED},
    FileStatus.ARCHIVED: {FileStatus.READY, FileStatus.DISABLED},
    FileStatus.REJECTED: {FileStatus.QUARANTINE},
}


StatusT = TypeVar("StatusT")


def _ensure_transition[StatusT](
    current: StatusT,
    target: StatusT,
    transitions: Mapping[StatusT, Set[StatusT]],
    *,
    entity_name: str,
) -> None:
    if target == current:
        return
    if target not in transitions[current]:
        raise InvalidStateTransition(
            f"Cannot transition {entity_name} from {current} to {target}.",
            safe_metadata={"entity": entity_name, "from": str(current), "to": str(target)},
        )


def apply_software_transition(
    software: Software,
    target: SoftwareStatus,
    *,
    now: datetime,
) -> Software:
    """Validate and apply one software lifecycle transition."""

    _ensure_transition(
        software.status,
        target,
        SOFTWARE_TRANSITIONS,
        entity_name="software",
    )
    if target == software.status:
        return software
    software.status = target
    if target is SoftwareStatus.PUBLISHED:
        software.published_at = software.published_at or now
        software.archived_at = None
    elif target is SoftwareStatus.ARCHIVED:
        software.archived_at = now
    else:
        software.archived_at = None
    return software


def apply_release_transition(
    release: Release,
    target: ReleaseStatus,
    *,
    now: datetime,
) -> Release:
    """Validate parent state and apply one release lifecycle transition."""

    _ensure_transition(release.status, target, RELEASE_TRANSITIONS, entity_name="release")
    if target == release.status:
        return release
    if target is ReleaseStatus.PUBLISHED and release.software.status not in {
        SoftwareStatus.PUBLISHED,
        SoftwareStatus.HIDDEN,
    }:
        raise InvalidStateTransition(
            "A release can be published only while its software is published or hidden.",
            safe_metadata={"entity": "release", "software_status": release.software.status},
        )
    release.status = target
    if target is ReleaseStatus.PUBLISHED:
        release.published_at = release.published_at or now
    else:
        release.is_current = False
    return release


def ensure_current_stable_candidate(release: Release) -> None:
    """Validate all invariants required by current stable selection."""

    if release.release_channel is not ReleaseChannel.STABLE:
        raise InvalidStateTransition("Only a stable release can be marked as current.")
    if release.status is not ReleaseStatus.PUBLISHED:
        raise InvalidStateTransition("Only a published release can be marked as current.")
    if release.software.status not in {SoftwareStatus.PUBLISHED, SoftwareStatus.HIDDEN}:
        raise InvalidStateTransition(
            "Current release selection requires published or hidden software."
        )


def apply_file_transition(
    release_file: ReleaseFile,
    target: FileStatus,
    *,
    now: datetime,
) -> ReleaseFile:
    """Validate and apply one release-file lifecycle transition."""

    _ensure_transition(release_file.status, target, FILE_TRANSITIONS, entity_name="file")
    if target == release_file.status:
        return release_file
    if target is FileStatus.READY and release_file.scanner_status is ScannerStatus.INFECTED:
        raise InvalidStateTransition("An infected file cannot be approved as ready.")
    if target is FileStatus.PUBLISHED:
        if release_file.release.status is not ReleaseStatus.PUBLISHED:
            raise InvalidStateTransition("A file requires a published release before publication.")
        if release_file.release.software.status not in {
            SoftwareStatus.PUBLISHED,
            SoftwareStatus.HIDDEN,
        }:
            raise InvalidStateTransition(
                "A file requires published or hidden software before publication."
            )
        if release_file.scanner_status is ScannerStatus.INFECTED:
            raise InvalidStateTransition("An infected file cannot be published.")
        release_file.published_at = release_file.published_at or now
        release_file.disabled_at = None
    elif target is FileStatus.DISABLED:
        release_file.disabled_at = now
    else:
        release_file.disabled_at = None
    release_file.status = target
    return release_file


def is_software_publicly_listed(software: Software) -> bool:
    """Return whether software belongs in public catalog listings."""

    return software.status is SoftwareStatus.PUBLISHED and software.visibility is Visibility.PUBLIC


def can_view_software(software: Software, *, is_admin: bool) -> bool:
    """Return whether a direct software page may be displayed."""

    if is_admin:
        return software.status is not SoftwareStatus.DISABLED
    return software.status in {
        SoftwareStatus.PUBLISHED,
        SoftwareStatus.ARCHIVED,
    } and software.visibility in {Visibility.PUBLIC, Visibility.UNLISTED}


def can_download_file(release_file: ReleaseFile, *, is_admin: bool) -> bool:
    """Evaluate the complete software → release → file authorization chain."""

    release = release_file.release
    software = release.software
    if release_file.status is not FileStatus.PUBLISHED:
        return False
    if release.status not in {ReleaseStatus.PUBLISHED, ReleaseStatus.ARCHIVED}:
        return False
    if software.status not in {SoftwareStatus.PUBLISHED, SoftwareStatus.ARCHIVED}:
        return False
    if is_admin:
        return True
    return software.visibility in {
        Visibility.PUBLIC,
        Visibility.UNLISTED,
    } and release_file.visibility in {Visibility.PUBLIC, Visibility.UNLISTED}
