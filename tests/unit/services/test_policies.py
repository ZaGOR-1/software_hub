"""Unit tests for pure domain lifecycle and visibility policies."""

from datetime import UTC, datetime

import pytest
from app.core.exceptions import InvalidStateTransition
from app.models import (
    FileStatus,
    Release,
    ReleaseChannel,
    ReleaseFile,
    ReleaseStatus,
    ScannerStatus,
    Software,
    SoftwareStatus,
    Visibility,
)
from app.services.policies import (
    FILE_TRANSITIONS,
    RELEASE_TRANSITIONS,
    SOFTWARE_TRANSITIONS,
    apply_file_transition,
    apply_release_transition,
    apply_software_transition,
    can_download_file,
    can_view_software,
    ensure_current_stable_candidate,
    is_software_publicly_listed,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)


def make_software(
    *,
    status: SoftwareStatus = SoftwareStatus.DRAFT,
    visibility: Visibility = Visibility.PRIVATE,
) -> Software:
    return Software(
        name="7-Zip",
        slug="7-zip",
        short_description="Archiver",
        status=status,
        visibility=visibility,
    )


def make_release(
    *,
    software_status: SoftwareStatus = SoftwareStatus.PUBLISHED,
    status: ReleaseStatus = ReleaseStatus.DRAFT,
    channel: ReleaseChannel = ReleaseChannel.STABLE,
) -> Release:
    return Release(
        software=make_software(status=software_status),
        version="26.00",
        release_channel=channel,
        status=status,
    )


def make_file(
    *,
    software_status: SoftwareStatus = SoftwareStatus.PUBLISHED,
    software_visibility: Visibility = Visibility.PUBLIC,
    release_status: ReleaseStatus = ReleaseStatus.PUBLISHED,
    file_status: FileStatus = FileStatus.READY,
    file_visibility: Visibility = Visibility.PUBLIC,
    scanner_status: ScannerStatus = ScannerStatus.CLEAN,
) -> ReleaseFile:
    software = make_software(status=software_status, visibility=software_visibility)
    release = Release(
        software=software,
        version="26.00",
        status=release_status,
        release_channel=ReleaseChannel.STABLE,
    )
    return ReleaseFile(
        release=release,
        original_filename="7z.exe",
        display_filename="7-Zip.exe",
        storage_filename="uuid.exe",
        relative_storage_path="7-zip/26/uuid.exe",
        file_extension=".exe",
        detected_mime_type="application/x-dosexec",
        file_size_bytes=10,
        sha256="a" * 64,
        platform="windows",
        status=file_status,
        visibility=file_visibility,
        scanner_status=scanner_status,
    )


def test_software_publish_and_archive_timestamps() -> None:
    software = make_software()

    apply_software_transition(software, SoftwareStatus.PUBLISHED, now=NOW)
    assert software.status is SoftwareStatus.PUBLISHED
    assert software.published_at == NOW

    apply_software_transition(software, SoftwareStatus.ARCHIVED, now=NOW)
    assert software.archived_at == NOW

    apply_software_transition(software, SoftwareStatus.HIDDEN, now=NOW)
    assert software.archived_at is None


def test_same_software_transition_is_idempotent() -> None:
    software = make_software(status=SoftwareStatus.PUBLISHED)
    assert apply_software_transition(software, SoftwareStatus.PUBLISHED, now=NOW) is software


def test_invalid_software_transition_is_rejected() -> None:
    software = make_software(status=SoftwareStatus.DISABLED)

    with pytest.raises(InvalidStateTransition, match="Cannot transition"):
        apply_software_transition(software, SoftwareStatus.PUBLISHED, now=NOW)


def test_release_publish_and_nonpublished_current_clear() -> None:
    release = make_release()

    apply_release_transition(release, ReleaseStatus.PUBLISHED, now=NOW)
    release.is_current = True
    assert release.published_at == NOW

    apply_release_transition(release, ReleaseStatus.ARCHIVED, now=NOW)
    assert release.is_current is False


def test_same_release_transition_is_idempotent() -> None:
    release = make_release(status=ReleaseStatus.DRAFT)
    assert apply_release_transition(release, ReleaseStatus.DRAFT, now=NOW) is release


def test_release_cannot_publish_under_draft_software() -> None:
    release = make_release(software_status=SoftwareStatus.DRAFT)

    with pytest.raises(InvalidStateTransition, match="software"):
        apply_release_transition(release, ReleaseStatus.PUBLISHED, now=NOW)


def test_invalid_release_transition_is_rejected() -> None:
    release = make_release(status=ReleaseStatus.DISABLED)

    with pytest.raises(InvalidStateTransition, match="Cannot transition"):
        apply_release_transition(release, ReleaseStatus.PUBLISHED, now=NOW)


def test_current_stable_candidate_requirements() -> None:
    ensure_current_stable_candidate(make_release(status=ReleaseStatus.PUBLISHED))

    with pytest.raises(InvalidStateTransition, match="stable"):
        ensure_current_stable_candidate(
            make_release(status=ReleaseStatus.PUBLISHED, channel=ReleaseChannel.BETA)
        )
    with pytest.raises(InvalidStateTransition, match="published release"):
        ensure_current_stable_candidate(make_release(status=ReleaseStatus.DRAFT))
    with pytest.raises(InvalidStateTransition, match="software"):
        ensure_current_stable_candidate(
            make_release(
                software_status=SoftwareStatus.ARCHIVED,
                status=ReleaseStatus.PUBLISHED,
            )
        )


def test_file_publish_sets_timestamps_and_disable_sets_disabled_at() -> None:
    release_file = make_file()

    apply_file_transition(release_file, FileStatus.PUBLISHED, now=NOW)
    assert release_file.published_at == NOW
    assert release_file.disabled_at is None

    apply_file_transition(release_file, FileStatus.DISABLED, now=NOW)
    assert release_file.disabled_at == NOW

    apply_file_transition(release_file, FileStatus.READY, now=NOW)
    assert release_file.disabled_at is None


def test_same_file_transition_is_idempotent() -> None:
    release_file = make_file()
    assert apply_file_transition(release_file, FileStatus.READY, now=NOW) is release_file


def test_file_publish_prerequisites() -> None:
    with pytest.raises(InvalidStateTransition, match="published release"):
        apply_file_transition(
            make_file(release_status=ReleaseStatus.DRAFT),
            FileStatus.PUBLISHED,
            now=NOW,
        )
    with pytest.raises(InvalidStateTransition, match="software"):
        apply_file_transition(
            make_file(software_status=SoftwareStatus.DRAFT),
            FileStatus.PUBLISHED,
            now=NOW,
        )
    with pytest.raises(InvalidStateTransition, match="infected"):
        apply_file_transition(
            make_file(scanner_status=ScannerStatus.INFECTED),
            FileStatus.PUBLISHED,
            now=NOW,
        )


def test_invalid_file_transition_is_rejected() -> None:
    release_file = make_file(file_status=FileStatus.QUARANTINE)

    with pytest.raises(InvalidStateTransition, match="Cannot transition"):
        apply_file_transition(release_file, FileStatus.PUBLISHED, now=NOW)


def test_software_listing_and_direct_visibility() -> None:
    public = make_software(
        status=SoftwareStatus.PUBLISHED,
        visibility=Visibility.PUBLIC,
    )
    unlisted = make_software(
        status=SoftwareStatus.PUBLISHED,
        visibility=Visibility.UNLISTED,
    )
    private = make_software(
        status=SoftwareStatus.PUBLISHED,
        visibility=Visibility.PRIVATE,
    )
    disabled = make_software(
        status=SoftwareStatus.DISABLED,
        visibility=Visibility.PUBLIC,
    )

    assert is_software_publicly_listed(public) is True
    assert is_software_publicly_listed(unlisted) is False
    assert can_view_software(unlisted, is_admin=False) is True
    assert can_view_software(private, is_admin=False) is False
    assert can_view_software(private, is_admin=True) is True
    assert can_view_software(disabled, is_admin=True) is False


def test_complete_download_visibility_chain() -> None:
    public_file = make_file(file_status=FileStatus.PUBLISHED)
    assert can_download_file(public_file, is_admin=False) is True

    private_file = make_file(
        file_status=FileStatus.PUBLISHED,
        file_visibility=Visibility.PRIVATE,
    )
    assert can_download_file(private_file, is_admin=False) is False
    assert can_download_file(private_file, is_admin=True) is True

    assert can_download_file(make_file(), is_admin=True) is False
    assert (
        can_download_file(
            make_file(
                file_status=FileStatus.PUBLISHED,
                release_status=ReleaseStatus.DRAFT,
            ),
            is_admin=True,
        )
        is False
    )
    assert (
        can_download_file(
            make_file(
                file_status=FileStatus.PUBLISHED,
                software_status=SoftwareStatus.DISABLED,
            ),
            is_admin=True,
        )
        is False
    )


@pytest.mark.parametrize("current", list(SoftwareStatus))
@pytest.mark.parametrize("target", list(SoftwareStatus))
def test_complete_software_transition_matrix(
    current: SoftwareStatus,
    target: SoftwareStatus,
) -> None:
    software = make_software(status=current)
    allowed = target == current or target in SOFTWARE_TRANSITIONS[current]

    if allowed:
        apply_software_transition(software, target, now=NOW)
        assert software.status is target
    else:
        with pytest.raises(InvalidStateTransition):
            apply_software_transition(software, target, now=NOW)


@pytest.mark.parametrize("current", list(ReleaseStatus))
@pytest.mark.parametrize("target", list(ReleaseStatus))
def test_complete_release_transition_matrix(
    current: ReleaseStatus,
    target: ReleaseStatus,
) -> None:
    release = make_release(status=current)
    allowed = target == current or target in RELEASE_TRANSITIONS[current]

    if allowed:
        apply_release_transition(release, target, now=NOW)
        assert release.status is target
    else:
        with pytest.raises(InvalidStateTransition):
            apply_release_transition(release, target, now=NOW)


@pytest.mark.parametrize("current", list(FileStatus))
@pytest.mark.parametrize("target", list(FileStatus))
def test_complete_file_transition_matrix(
    current: FileStatus,
    target: FileStatus,
) -> None:
    release_file = make_file(file_status=current)
    allowed = target == current or target in FILE_TRANSITIONS[current]

    if allowed:
        apply_file_transition(release_file, target, now=NOW)
        assert release_file.status is target
    else:
        with pytest.raises(InvalidStateTransition):
            apply_file_transition(release_file, target, now=NOW)
