"""Public catalog orchestration and ORM-to-view-model projection."""

from __future__ import annotations

from datetime import date, datetime
from typing import overload
from urllib.parse import quote

from app.core.exceptions import EntityNotFound, ValidationError
from app.database.session import Database
from app.models.enums import (
    Architecture,
    FileStatus,
    PackageType,
    ReleaseChannel,
    ReleaseStatus,
    SignatureStatus,
    SoftwareStatus,
    Visibility,
)
from app.models.release import Release
from app.models.release_file import ReleaseFile
from app.models.software import Software
from app.repositories.public_catalog_repository import PublicCatalogRepository
from app.repositories.software_repository import (
    SoftwareFilters,
    SoftwareRepository,
    SoftwareSort,
    normalize_search_query,
)
from app.schemas.pagination import Page, Pagination
from app.schemas.public_catalog import (
    CatalogFacet,
    PublicCatalogView,
    PublicFileView,
    PublicHomeView,
    PublicReleaseView,
    SitemapEntry,
    SoftwareCardView,
    SoftwareDetailView,
)
from app.services.policies import can_view_software

_ARCHITECTURE_LABELS = {
    Architecture.X64: "x64",
    Architecture.X86: "x86",
    Architecture.ARM64: "ARM64",
    Architecture.UNIVERSAL: "Універсальна",
    Architecture.OTHER: "Інша",
}
_PACKAGE_LABELS = {
    PackageType.INSTALLER: "Інсталятор",
    PackageType.PORTABLE: "Portable",
    PackageType.ARCHIVE: "Архів",
    PackageType.MSI: "MSI",
    PackageType.OTHER: "Інший пакет",
}
_CHANNEL_LABELS = {
    ReleaseChannel.STABLE: "Stable",
    ReleaseChannel.BETA: "Beta",
    ReleaseChannel.ALPHA: "Alpha",
    ReleaseChannel.NIGHTLY: "Nightly",
    ReleaseChannel.LEGACY: "Legacy",
}
_SIGNATURE_LABELS = {
    SignatureStatus.VALID: "Підпис перевірено",
    SignatureStatus.INVALID: "Підпис недійсний",
    SignatureStatus.UNSIGNED: "Без цифрового підпису",
    SignatureStatus.NOT_CHECKED: "Підпис не перевірявся",
    SignatureStatus.UNKNOWN: "Статус підпису невідомий",
}


class PublicCatalogService:
    """Build bounded public pages without exposing raw ORM entities to templates."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def home(self) -> PublicHomeView:
        """Return the bounded category, featured, latest and popular sections."""

        with self.database.session() as session:
            facets = PublicCatalogRepository(session)
            software = SoftwareRepository(session)
            base = SoftwareFilters(
                statuses=(SoftwareStatus.PUBLISHED,),
                visibilities=(Visibility.PUBLIC,),
                public_facets_only=True,
            )
            featured_page = software.list_page(
                Pagination(page=1, per_page=6),
                SoftwareFilters(
                    statuses=base.statuses,
                    visibilities=base.visibilities,
                    sort=SoftwareSort.UPDATED,
                    is_featured=True,
                    public_facets_only=True,
                ),
            )
            latest_page = software.list_page(
                Pagination(page=1, per_page=8),
                base,
            )
            popular_page = software.list_page(
                Pagination(page=1, per_page=8),
                SoftwareFilters(
                    statuses=base.statuses,
                    visibilities=base.visibilities,
                    sort=SoftwareSort.POPULARITY,
                    public_facets_only=True,
                ),
            )
            return PublicHomeView(
                categories=facets.list_categories(limit=12),
                featured=tuple(_software_card(item) for item in featured_page.items),
                latest=tuple(_software_card(item) for item in latest_page.items),
                popular=tuple(_software_card(item) for item in popular_page.items),
            )

    def catalog(
        self,
        *,
        pagination: Pagination,
        query: str | None = None,
        category_slug: str | None = None,
        tag_slug: str | None = None,
        sort: SoftwareSort = SoftwareSort.UPDATED,
    ) -> PublicCatalogView:
        """Return one public catalog page and validated filter facets."""

        try:
            normalized_query = normalize_search_query(query)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        with self.database.session() as session:
            facets = PublicCatalogRepository(session)
            category = facets.get_category(category_slug) if category_slug else None
            if category_slug is not None and category is None:
                raise EntityNotFound("Категорію не знайдено.")
            tag = facets.get_tag(tag_slug) if tag_slug else None
            if tag_slug is not None and tag is None:
                raise EntityNotFound("Тег не знайдено.")

            page = SoftwareRepository(session).list_page(
                pagination,
                SoftwareFilters(
                    query=normalized_query,
                    category_slug=category.slug if category else None,
                    tag_slugs=(tag.slug,) if tag else (),
                    statuses=(SoftwareStatus.PUBLISHED,),
                    visibilities=(Visibility.PUBLIC,),
                    sort=sort,
                    public_facets_only=True,
                ),
            )
            public_page = Page(
                items=tuple(_software_card(item) for item in page.items),
                total=page.total,
                page=page.page,
                per_page=page.per_page,
            )
            return PublicCatalogView(
                page=public_page,
                categories=facets.list_categories(),
                tags=facets.list_tags(),
                query=normalized_query or "",
                category=category,
                tag=tag,
                sort=sort.value,
            )

    def sitemap_entries(self) -> tuple[SitemapEntry, ...]:
        """Return bounded public paths for the XML sitemap."""

        with self.database.session() as session:
            return PublicCatalogRepository(session).list_sitemap_entries()

    def software(self, slug: str, *, is_admin: bool) -> SoftwareDetailView:
        """Return one direct software page under public visibility rules."""

        with self.database.session() as session:
            software = SoftwareRepository(session).get_by_slug(slug)
            if software is None or not can_view_software(software, is_admin=is_admin):
                raise EntityNotFound("Програму не знайдено.")
            return _software_detail(software, is_admin=is_admin)


def _software_card(software: Software) -> SoftwareCardView:
    releases = _release_views(software, is_admin=False)
    current = _current_release(releases)
    recommended = _recommended_file(current)
    return SoftwareCardView(
        name=software.name,
        slug=software.slug,
        initials=_initials(software.name),
        short_description=software.short_description,
        category=_category_facet(software, is_admin=False),
        tags=_tag_facets(software),
        current_version=current.version if current else None,
        updated_at=software.updated_at,
        updated_at_label=_date_label(software.updated_at),
        total_downloads=sum(file.download_count for release in releases for file in release.files),
        recommended_file=recommended,
        is_featured=software.is_featured,
    )


def _software_detail(software: Software, *, is_admin: bool) -> SoftwareDetailView:
    releases = _release_views(software, is_admin=is_admin)
    current = _current_release(releases)
    return SoftwareDetailView(
        name=software.name,
        slug=software.slug,
        initials=_initials(software.name),
        short_description=software.short_description,
        full_description=software.full_description,
        developer_name=software.developer_name,
        official_website_url=software.official_website_url,
        source_url=software.source_url,
        license_name=software.license_name,
        supported_os=software.supported_os,
        system_requirements=software.system_requirements,
        category=_category_facet(software, is_admin=is_admin),
        tags=_tag_facets(software),
        status=software.status,
        visibility=software.visibility,
        is_featured=software.is_featured,
        is_archived=software.status is SoftwareStatus.ARCHIVED,
        is_unlisted=software.visibility is Visibility.UNLISTED,
        is_private=software.visibility is Visibility.PRIVATE,
        published_at=software.published_at,
        published_at_label=_date_label(software.published_at),
        updated_at=software.updated_at,
        updated_at_label=_date_label(software.updated_at),
        current_release=current,
        releases=releases,
        recommended_file=_recommended_file(current),
        total_downloads=sum(file.download_count for release in releases for file in release.files),
    )


def _release_views(
    software: Software,
    *,
    is_admin: bool,
) -> tuple[PublicReleaseView, ...]:
    eligible = [
        release
        for release in software.releases
        if release.status in {ReleaseStatus.PUBLISHED, ReleaseStatus.ARCHIVED}
    ]
    eligible.sort(key=_release_sort_key, reverse=True)
    return tuple(_release_view(release, is_admin=is_admin) for release in eligible)


def _release_sort_key(release: Release) -> tuple[bool, date, int]:
    return (
        release.is_current,
        release.release_date or date.min,
        release.id,
    )


def _release_view(release: Release, *, is_admin: bool) -> PublicReleaseView:
    files = tuple(
        _file_view(file)
        for file in sorted(release.files, key=_file_sort_key)
        if _is_listable_file(file, is_admin=is_admin)
    )
    return PublicReleaseView(
        version=release.version,
        channel=release.release_channel,
        channel_label=_CHANNEL_LABELS[release.release_channel],
        release_date=release.release_date,
        release_date_label=_date_label(release.release_date),
        changelog=release.changelog,
        is_current=release.is_current and release.status is ReleaseStatus.PUBLISHED,
        is_archived=release.status is ReleaseStatus.ARCHIVED,
        files=files,
    )


def _is_listable_file(file: ReleaseFile, *, is_admin: bool) -> bool:
    if file.status is not FileStatus.PUBLISHED:
        return False
    if is_admin:
        return True
    return file.visibility is Visibility.PUBLIC


def _file_sort_key(file: ReleaseFile) -> tuple[int, int, str, int]:
    architecture_order = {
        Architecture.X64: 0,
        Architecture.ARM64: 1,
        Architecture.X86: 2,
        Architecture.UNIVERSAL: 3,
        Architecture.OTHER: 4,
    }
    package_order = {
        PackageType.INSTALLER: 0,
        PackageType.MSI: 1,
        PackageType.PORTABLE: 2,
        PackageType.ARCHIVE: 3,
        PackageType.OTHER: 4,
    }
    return (
        architecture_order[file.architecture],
        package_order[file.package_type],
        file.display_filename.casefold(),
        file.id,
    )


def _file_view(file: ReleaseFile) -> PublicFileView:
    encoded_name = quote(file.display_filename, safe="", encoding="utf-8")
    return PublicFileView(
        public_uuid=file.public_uuid,
        display_filename=file.display_filename,
        download_path=f"/download/{file.public_uuid}/{encoded_name}",
        architecture=file.architecture,
        architecture_label=_ARCHITECTURE_LABELS[file.architecture],
        package_type=file.package_type,
        package_type_label=_PACKAGE_LABELS[file.package_type],
        platform=file.platform,
        edition=file.edition,
        file_size_bytes=file.file_size_bytes,
        file_size_label=_format_bytes(file.file_size_bytes),
        sha256=file.sha256,
        download_count=file.download_count,
        published_at=file.published_at,
        published_at_label=_date_label(file.published_at),
        signature_label=_SIGNATURE_LABELS[file.signature_status],
    )


def _current_release(
    releases: tuple[PublicReleaseView, ...],
) -> PublicReleaseView | None:
    current = next((release for release in releases if release.is_current), None)
    if current is not None:
        return current
    return next(
        (
            release
            for release in releases
            if release.channel is ReleaseChannel.STABLE and not release.is_archived
        ),
        None,
    )


def _recommended_file(release: PublicReleaseView | None) -> PublicFileView | None:
    if release is None or not release.files:
        return None
    return release.files[0]


def _category_facet(
    software: Software,
    *,
    is_admin: bool,
) -> CatalogFacet | None:
    category = software.category
    if category is None or (not category.is_visible and not is_admin):
        return None
    return CatalogFacet(
        name=category.name,
        slug=category.slug,
        description=category.description,
        software_count=0,
    )


def _tag_facets(software: Software) -> tuple[CatalogFacet, ...]:
    return tuple(
        CatalogFacet(
            name=tag.name,
            slug=tag.slug,
            description=None,
            software_count=0,
        )
        for tag in sorted(software.tags, key=lambda item: (item.name.casefold(), item.id))
    )


@overload
def _date_label(value: None) -> None: ...


@overload
def _date_label(value: date | datetime) -> str: ...


def _date_label(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d.%m.%Y")


def _format_bytes(size: int) -> str:
    value = float(size)
    units = ("Б", "КіБ", "МіБ", "ГіБ", "ТіБ")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} Б"


def _initials(name: str) -> str:
    words = [word for word in name.replace("-", " ").split() if word]
    if not words:
        return "SH"
    if len(words) == 1:
        return words[0][:2].upper()
    return f"{words[0][0]}{words[1][0]}".upper()
