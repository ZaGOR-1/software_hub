"""Integration tests for transaction-oriented Phase 5 application services."""

from datetime import date

import pytest
from app.core.exceptions import (
    EntityConflict,
    EntityNotFound,
    InvalidStateTransition,
    ValidationError,
)
from app.database.session import Database
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
from app.repositories.software_repository import SoftwareFilters, SoftwareSort
from app.schemas.pagination import Pagination
from app.services import (
    CategoryService,
    FileService,
    ReleaseService,
    SoftwareService,
    TagService,
)
from sqlalchemy import select


def test_category_service_create_update_list_and_conflicts(
    domain_database: Database,
) -> None:
    service = CategoryService(domain_database)
    category = service.create(
        name="  System   Tools ",
        slug="SYSTEM__TOOLS",
        description="Utilities",
        sort_order=2,
    )
    assert category.name == "System Tools"
    assert category.slug == "system-tools"

    updated = service.update(
        category.id,
        name="Utilities",
        slug="utilities",
        description=None,
        sort_order=1,
        is_visible=False,
    )
    assert updated.slug == "utilities"
    assert service.list(Pagination(), visible_only=True).total == 0
    assert service.list(Pagination()).total == 1

    with pytest.raises(EntityConflict):
        service.create(name="Duplicate", slug="utilities")
    with pytest.raises(ValidationError):
        service.create(name="Bad", slug="bad slug")
    with pytest.raises(ValidationError):
        service.create(name="Bad", slug="bad", sort_order=-1)
    with pytest.raises(ValidationError):
        service.update(
            category.id,
            name="Bad",
            slug="bad",
            description=None,
            sort_order=-1,
            is_visible=True,
        )
    with pytest.raises(EntityNotFound):
        service.update(
            999,
            name="Missing",
            slug="missing",
            description=None,
            sort_order=0,
            is_visible=True,
        )

    other = service.create(name="Other", slug="other")
    with pytest.raises(EntityConflict):
        service.update(
            other.id,
            name="Other",
            slug="utilities",
            description=None,
            sort_order=0,
            is_visible=True,
        )


def test_tag_service_create_update_list_and_conflicts(domain_database: Database) -> None:
    service = TagService(domain_database)
    tag = service.create(name="  Open   Source ", slug="OPEN__SOURCE")
    assert tag.name == "Open Source"
    assert tag.slug == "open-source"

    updated = service.update(tag.id, name="FOSS", slug="foss")
    assert updated.name == "FOSS"
    assert service.list(Pagination()).items[0].slug == "foss"

    with pytest.raises(EntityConflict):
        service.create(name="Duplicate", slug="foss")
    with pytest.raises(ValidationError):
        service.create(name="", slug="empty")
    with pytest.raises(EntityNotFound):
        service.update(999, name="Missing", slug="missing")

    other = service.create(name="Other", slug="other")
    with pytest.raises(EntityConflict):
        service.update(other.id, name="Other", slug="foss")


def test_software_service_creation_search_tags_and_visibility(
    domain_database: Database,
) -> None:
    category = CategoryService(domain_database).create(name="Archivers", slug="archivers")
    utility = TagService(domain_database).create(name="Utility", slug="utility")
    portable = TagService(domain_database).create(name="Portable", slug="portable")
    service = SoftwareService(domain_database)

    software = service.create(
        name="  Seven   Zip ",
        slug="SEVEN__ZIP",
        short_description="  Fast   file archiver ",
        category_id=category.id,
        tag_ids=[utility.id],
    )
    assert software.name == "Seven Zip"
    assert software.slug == "seven-zip"
    assert software.short_description == "Fast file archiver"
    assert software.status is SoftwareStatus.DRAFT
    assert software.visibility is Visibility.PRIVATE

    loaded = service.get(software.id)
    assert loaded.category is not None
    assert loaded.category.slug == "archivers"
    assert [tag.slug for tag in loaded.tags] == ["utility"]

    replaced = service.replace_tags(software.id, [portable.id, utility.id, portable.id])
    assert {tag.slug for tag in replaced.tags} == {"utility", "portable"}

    service.set_visibility(software.id, Visibility.PUBLIC)
    service.transition_status(software.id, SoftwareStatus.PUBLISHED)
    page = service.list(
        Pagination(),
        SoftwareFilters(
            query="file archiver",
            statuses=(SoftwareStatus.PUBLISHED,),
            visibilities=(Visibility.PUBLIC,),
            sort=SoftwareSort.NAME,
        ),
    )
    assert [item.id for item in page.items] == [software.id]

    with pytest.raises(EntityConflict):
        service.create(name="Duplicate", slug="seven-zip", short_description="Duplicate")
    with pytest.raises(ValidationError):
        service.create(name="Bad", slug="bad", short_description="   ")
    with pytest.raises(ValidationError):
        service.list(Pagination(), SoftwareFilters(query="x"))
    with pytest.raises(EntityNotFound):
        service.create(
            name="No Category",
            slug="no-category",
            short_description="Missing",
            category_id=999,
        )
    with pytest.raises(EntityNotFound):
        service.create(
            name="No Tag",
            slug="no-tag",
            short_description="Missing",
            tag_ids=[999],
        )
    with pytest.raises(EntityNotFound):
        service.get(999)
    with pytest.raises(EntityNotFound):
        service.replace_tags(software.id, [999])
    with pytest.raises(EntityNotFound):
        service.replace_tags(999, [])
    with pytest.raises(EntityNotFound):
        service.transition_status(999, SoftwareStatus.PUBLISHED)
    with pytest.raises(EntityNotFound):
        service.set_visibility(999, Visibility.PUBLIC)


def test_software_invalid_transition_rolls_back(domain_database: Database) -> None:
    service = SoftwareService(domain_database)
    software = service.create(name="Tool", slug="tool", short_description="Tool")
    service.transition_status(software.id, SoftwareStatus.DISABLED)

    with pytest.raises(InvalidStateTransition):
        service.transition_status(software.id, SoftwareStatus.PUBLISHED)

    assert service.get(software.id).status is SoftwareStatus.DISABLED
    restored = service.transition_status(software.id, SoftwareStatus.DRAFT)
    assert restored.status is SoftwareStatus.DRAFT


def test_release_service_creation_transitions_and_current_selection(
    domain_database: Database,
) -> None:
    software_service = SoftwareService(domain_database)
    release_service = ReleaseService(domain_database)
    software = software_service.create(name="Tool", slug="tool", short_description="Tool")

    first = release_service.create(
        software_id=software.id,
        version=" 1.0 ",
        release_date=date(2026, 1, 1),
    )
    second = release_service.create(
        software_id=software.id,
        version="2.0",
        release_date=date(2026, 2, 1),
    )
    beta = release_service.create(
        software_id=software.id,
        version="3.0-beta",
        release_channel=ReleaseChannel.BETA,
    )
    assert first.version == "1.0"
    assert release_service.list_for_software(software.id, Pagination()).total == 3

    with pytest.raises(InvalidStateTransition, match="software"):
        release_service.transition_status(first.id, ReleaseStatus.PUBLISHED)

    software_service.transition_status(software.id, SoftwareStatus.PUBLISHED)
    release_service.transition_status(first.id, ReleaseStatus.PUBLISHED)
    release_service.transition_status(second.id, ReleaseStatus.PUBLISHED)
    release_service.transition_status(beta.id, ReleaseStatus.PUBLISHED)

    current_first = release_service.set_current_stable(first.id)
    assert current_first.is_current is True
    current_second = release_service.set_current_stable(second.id)
    assert current_second.is_current is True

    with domain_database.session() as session:
        releases = list(
            session.scalars(
                select(Release).where(Release.software_id == software.id).order_by(Release.version)
            ).all()
        )
        current_ids = [release.id for release in releases if release.is_current]
        assert current_ids == [second.id]

    archived = release_service.transition_status(second.id, ReleaseStatus.ARCHIVED)
    assert archived.is_current is False

    with pytest.raises(InvalidStateTransition, match="stable"):
        release_service.set_current_stable(beta.id)
    draft = release_service.create(software_id=software.id, version="4.0")
    with pytest.raises(InvalidStateTransition, match="published release"):
        release_service.set_current_stable(draft.id)
    with pytest.raises(EntityConflict):
        release_service.create(software_id=software.id, version="1.0")
    with pytest.raises(ValidationError):
        release_service.create(software_id=software.id, version="   ")
    with pytest.raises(EntityNotFound):
        release_service.create(software_id=999, version="1.0")
    with pytest.raises(EntityNotFound):
        release_service.list_for_software(999, Pagination())
    with pytest.raises(EntityNotFound):
        release_service.transition_status(999, ReleaseStatus.PUBLISHED)
    with pytest.raises(EntityNotFound):
        release_service.set_current_stable(999)


def seed_ready_files(database: Database) -> tuple[int, int, str]:
    with database.transaction() as session:
        software = Software(
            name="Tool",
            slug="tool",
            short_description="Tool",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        release = Release(
            software=software,
            version="1.0",
            release_channel=ReleaseChannel.STABLE,
            status=ReleaseStatus.PUBLISHED,
        )
        first = ReleaseFile(
            release=release,
            original_filename="tool.exe",
            display_filename="tool.exe",
            storage_filename="one.exe",
            relative_storage_path="tool/one.exe",
            file_extension=".exe",
            detected_mime_type="application/x-dosexec",
            file_size_bytes=10,
            sha256="d" * 64,
            platform="windows",
            status=FileStatus.READY,
            visibility=Visibility.PRIVATE,
            scanner_status=ScannerStatus.CLEAN,
        )
        second = ReleaseFile(
            release=release,
            original_filename="copy.exe",
            display_filename="copy.exe",
            storage_filename="two.exe",
            relative_storage_path="tool/two.exe",
            file_extension=".exe",
            detected_mime_type="application/x-dosexec",
            file_size_bytes=10,
            sha256="d" * 64,
            platform="windows",
            status=FileStatus.READY,
            visibility=Visibility.PRIVATE,
            scanner_status=ScannerStatus.CLEAN,
        )
        session.add(software)
        session.flush()
        return first.id, second.id, first.sha256


def test_file_service_duplicates_lifecycle_visibility_and_failures(
    domain_database: Database,
) -> None:
    first_id, second_id, digest = seed_ready_files(domain_database)
    service = FileService(domain_database)

    assert (
        service.list_for_release(
            service.find_duplicates(digest)[0].release_id,
            Pagination(),
        ).total
        == 2
    )
    assert [item.id for item in service.find_duplicates(digest)] == [first_id, second_id]
    assert [item.id for item in service.find_duplicates(digest, exclude_file_id=first_id)] == [
        second_id
    ]

    published = service.transition_status(first_id, FileStatus.PUBLISHED)
    assert published.published_at is not None
    public_file = service.set_visibility(first_id, Visibility.PUBLIC)
    assert public_file.visibility is Visibility.PUBLIC
    disabled = service.transition_status(first_id, FileStatus.DISABLED)
    assert disabled.disabled_at is not None
    ready = service.transition_status(first_id, FileStatus.READY)
    assert ready.disabled_at is None

    with pytest.raises(ValidationError):
        service.find_duplicates("bad")
    with pytest.raises(EntityNotFound):
        service.transition_status(999, FileStatus.PUBLISHED)
    with pytest.raises(EntityNotFound):
        service.set_visibility(999, Visibility.PUBLIC)


def test_infected_file_publish_rolls_back(domain_database: Database) -> None:
    first_id, _, _ = seed_ready_files(domain_database)
    with domain_database.transaction() as session:
        release_file = session.get(ReleaseFile, first_id)
        assert release_file is not None
        release_file.scanner_status = ScannerStatus.INFECTED

    service = FileService(domain_database)
    with pytest.raises(InvalidStateTransition, match="infected"):
        service.transition_status(first_id, FileStatus.PUBLISHED)

    with domain_database.session() as session:
        release_file = session.get(ReleaseFile, first_id)
        assert release_file is not None
        assert release_file.status is FileStatus.READY
