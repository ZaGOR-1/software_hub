"""Immutable presentation models for the server-rendered public catalog."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.models.enums import (
    Architecture,
    PackageType,
    ReleaseChannel,
    SoftwareStatus,
    Visibility,
)
from app.schemas.pagination import Page


@dataclass(frozen=True, slots=True)
class CatalogFacet:
    """One public category or tag with its visible software count."""

    name: str
    slug: str
    description: str | None
    software_count: int


@dataclass(frozen=True, slots=True)
class PublicFileView:
    """Public-safe metadata for one downloadable release file."""

    public_uuid: UUID
    display_filename: str
    download_path: str
    architecture: Architecture
    architecture_label: str
    package_type: PackageType
    package_type_label: str
    platform: str
    edition: str | None
    file_size_bytes: int
    file_size_label: str
    sha256: str
    download_count: int
    published_at: datetime | None
    published_at_label: str | None
    signature_label: str


@dataclass(frozen=True, slots=True)
class PublicReleaseView:
    """Public-safe release metadata and its listable files."""

    version: str
    channel: ReleaseChannel
    channel_label: str
    release_date: date | None
    release_date_label: str | None
    changelog: str | None
    is_current: bool
    is_archived: bool
    files: tuple[PublicFileView, ...]


@dataclass(frozen=True, slots=True)
class SoftwareCardView:
    """Compact catalog card detached from the ORM session."""

    name: str
    slug: str
    initials: str
    short_description: str
    category: CatalogFacet | None
    tags: tuple[CatalogFacet, ...]
    current_version: str | None
    updated_at: datetime
    updated_at_label: str
    total_downloads: int
    recommended_file: PublicFileView | None
    is_featured: bool


@dataclass(frozen=True, slots=True)
class SoftwareDetailView:
    """Complete public software page without private storage metadata."""

    name: str
    slug: str
    initials: str
    short_description: str
    full_description: str | None
    developer_name: str | None
    official_website_url: str | None
    source_url: str | None
    license_name: str | None
    supported_os: str | None
    system_requirements: str | None
    category: CatalogFacet | None
    tags: tuple[CatalogFacet, ...]
    status: SoftwareStatus
    visibility: Visibility
    is_featured: bool
    is_archived: bool
    is_unlisted: bool
    is_private: bool
    published_at: datetime | None
    published_at_label: str | None
    updated_at: datetime
    updated_at_label: str
    current_release: PublicReleaseView | None
    releases: tuple[PublicReleaseView, ...]
    recommended_file: PublicFileView | None
    total_downloads: int


@dataclass(frozen=True, slots=True)
class PublicCatalogView:
    """Catalog result and the public facets used by its filter controls."""

    page: Page[SoftwareCardView]
    categories: tuple[CatalogFacet, ...]
    tags: tuple[CatalogFacet, ...]
    query: str
    category: CatalogFacet | None
    tag: CatalogFacet | None
    sort: str


@dataclass(frozen=True, slots=True)
class PublicHomeView:
    """Home-page sections assembled from independent bounded queries."""

    categories: tuple[CatalogFacet, ...]
    featured: tuple[SoftwareCardView, ...]
    latest: tuple[SoftwareCardView, ...]
    popular: tuple[SoftwareCardView, ...]


@dataclass(frozen=True, slots=True)
class SitemapEntry:
    """One trusted public path exposed through the XML sitemap."""

    path: str
    last_modified: date | datetime | None = None
