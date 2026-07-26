"""Software catalog persistence and parameterized search queries."""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.associations import software_tags
from app.models.category import Category
from app.models.enums import FileStatus, ReleaseStatus, SoftwareStatus, Visibility
from app.models.release import Release
from app.models.release_file import ReleaseFile
from app.models.software import Software
from app.models.tag import Tag
from app.repositories.base import BaseRepository, paginate_scalars
from app.schemas.pagination import Page, Pagination


class SoftwareSort(StrEnum):
    """Supported safe software ordering modes."""

    NAME = "name"
    UPDATED = "updated"
    POPULARITY = "popularity"


@dataclass(frozen=True, slots=True)
class SoftwareFilters:
    """Typed filters used by admin and future public catalog services."""

    query: str | None = None
    category_slug: str | None = None
    tag_slugs: tuple[str, ...] = ()
    statuses: tuple[SoftwareStatus, ...] = ()
    visibilities: tuple[Visibility, ...] = ()
    sort: SoftwareSort = SoftwareSort.UPDATED
    is_featured: bool | None = None
    public_facets_only: bool = False


def normalize_search_query(query: str | None) -> str | None:
    """Collapse whitespace and enforce defensive search length bounds."""

    if query is None:
        return None
    normalized = " ".join(query.split())
    if not normalized:
        return None
    if len(normalized) < 2:
        msg = "Search query must contain at least 2 characters."
        raise ValueError(msg)
    if len(normalized) > 100:
        msg = "Search query must not exceed 100 characters."
        raise ValueError(msg)
    return normalized


def escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters while preserving bind parameters."""

    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SoftwareRepository(BaseRepository[Software]):
    """Session-bound software CRUD, eager loading and catalog search."""

    model = Software

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    @staticmethod
    def _with_summary_graph(statement: Select[tuple[Software]]) -> Select[tuple[Software]]:
        return statement.options(
            selectinload(Software.category),
            selectinload(Software.tags),
            selectinload(Software.releases).selectinload(Release.files),
        )

    def get_with_graph(self, software_id: int) -> Software | None:
        """Return software with category, tags, releases and file metadata loaded."""

        statement = self._with_summary_graph(select(Software).where(Software.id == software_id))
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> Software | None:
        """Return software by normalized slug with its summary graph loaded."""

        statement = self._with_summary_graph(
            select(Software).where(Software.slug == slug.strip().casefold())
        )
        return self.session.scalar(statement)

    def list_page(
        self,
        pagination: Pagination,
        filters: SoftwareFilters | None = None,
    ) -> Page[Software]:
        """Return a safely filtered, parameterized and eagerly loaded software page."""

        selected_filters = filters or SoftwareFilters()
        normalized_query = normalize_search_query(selected_filters.query)
        statement = select(Software)
        joins_category = selected_filters.category_slug is not None or normalized_query is not None
        joins_tags = bool(selected_filters.tag_slugs) or normalized_query is not None

        if joins_category:
            statement = statement.outerjoin(Category, Software.category_id == Category.id)
        if joins_tags:
            statement = statement.outerjoin(software_tags).outerjoin(Tag)

        if normalized_query is not None:
            pattern = f"%{escape_like(normalized_query)}%"
            category_search: ColumnElement[bool] = Category.name.ilike(pattern, escape="\\")
            if selected_filters.public_facets_only:
                category_search = and_(Category.is_visible.is_(True), category_search)
            statement = statement.where(
                or_(
                    Software.name.ilike(pattern, escape="\\"),
                    Software.short_description.ilike(pattern, escape="\\"),
                    Software.developer_name.ilike(pattern, escape="\\"),
                    category_search,
                    Tag.name.ilike(pattern, escape="\\"),
                )
            )
        if selected_filters.category_slug is not None:
            statement = statement.where(
                Category.slug == selected_filters.category_slug.strip().casefold()
            )
            if selected_filters.public_facets_only:
                statement = statement.where(Category.is_visible.is_(True))
        if selected_filters.tag_slugs:
            normalized_tags = tuple(slug.strip().casefold() for slug in selected_filters.tag_slugs)
            statement = statement.where(Tag.slug.in_(normalized_tags))
        if selected_filters.statuses:
            statement = statement.where(Software.status.in_(selected_filters.statuses))
        if selected_filters.visibilities:
            statement = statement.where(Software.visibility.in_(selected_filters.visibilities))
        if selected_filters.is_featured is not None:
            statement = statement.where(Software.is_featured.is_(selected_filters.is_featured))

        statement = statement.distinct()
        if selected_filters.sort is SoftwareSort.NAME:
            statement = statement.order_by(func.lower(Software.name), Software.id)
        elif selected_filters.sort is SoftwareSort.POPULARITY:
            popularity_statement = (
                select(func.coalesce(func.sum(ReleaseFile.download_count), 0))
                .join(Release, Release.id == ReleaseFile.release_id)
                .where(Release.software_id == Software.id)
            )
            if selected_filters.public_facets_only:
                popularity_statement = popularity_statement.where(
                    Release.status.in_((ReleaseStatus.PUBLISHED, ReleaseStatus.ARCHIVED)),
                    ReleaseFile.status == FileStatus.PUBLISHED,
                    ReleaseFile.visibility == Visibility.PUBLIC,
                )
            popularity = popularity_statement.correlate(Software).scalar_subquery()
            statement = statement.order_by(popularity.desc(), func.lower(Software.name))
        else:
            statement = statement.order_by(Software.updated_at.desc(), Software.id.desc())

        return paginate_scalars(
            self.session,
            self._with_summary_graph(statement),
            pagination,
        )
