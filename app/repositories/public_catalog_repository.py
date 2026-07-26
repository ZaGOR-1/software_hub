"""Public-only category and tag facet queries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.associations import software_tags
from app.models.category import Category
from app.models.enums import SoftwareStatus, Visibility
from app.models.software import Software
from app.models.tag import Tag
from app.schemas.public_catalog import CatalogFacet, SitemapEntry


class PublicCatalogRepository:
    """Read-only queries that never expose facets from private catalog records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_categories(self, *, limit: int = 100) -> tuple[CatalogFacet, ...]:
        """Return visible categories that contain publicly listed software."""

        count = func.count(func.distinct(Software.id))
        statement = (
            select(
                Category.name,
                Category.slug,
                Category.description,
                count.label("software_count"),
            )
            .join(Software, Software.category_id == Category.id)
            .where(
                Category.is_visible.is_(True),
                Software.status == SoftwareStatus.PUBLISHED,
                Software.visibility == Visibility.PUBLIC,
            )
            .group_by(Category.id, Category.name, Category.slug, Category.description)
            .order_by(Category.sort_order, func.lower(Category.name), Category.id)
            .limit(limit)
        )
        return tuple(
            CatalogFacet(
                name=row.name,
                slug=row.slug,
                description=row.description,
                software_count=int(row.software_count),
            )
            for row in self.session.execute(statement)
        )

    def list_tags(self, *, limit: int = 100) -> tuple[CatalogFacet, ...]:
        """Return tags attached to at least one publicly listed software entry."""

        count = func.count(func.distinct(Software.id))
        statement = (
            select(Tag.name, Tag.slug, count.label("software_count"))
            .join(software_tags, software_tags.c.tag_id == Tag.id)
            .join(Software, Software.id == software_tags.c.software_id)
            .where(
                Software.status == SoftwareStatus.PUBLISHED,
                Software.visibility == Visibility.PUBLIC,
            )
            .group_by(Tag.id, Tag.name, Tag.slug)
            .order_by(count.desc(), func.lower(Tag.name), Tag.id)
            .limit(limit)
        )
        return tuple(
            CatalogFacet(
                name=row.name,
                slug=row.slug,
                description=None,
                software_count=int(row.software_count),
            )
            for row in self.session.execute(statement)
        )

    def list_sitemap_entries(self, *, limit: int = 24_000) -> tuple[SitemapEntry, ...]:
        """Return only indexable public software and category paths."""

        categories = self.list_categories(limit=1_000)
        statement = (
            select(Software.slug, Software.updated_at)
            .where(
                Software.status == SoftwareStatus.PUBLISHED,
                Software.visibility == Visibility.PUBLIC,
            )
            .order_by(func.lower(Software.slug), Software.id)
            .limit(limit)
        )
        entries: list[SitemapEntry] = [
            SitemapEntry(path="/"),
            SitemapEntry(path="/software"),
        ]
        entries.extend(SitemapEntry(path=f"/category/{category.slug}") for category in categories)
        for row in self.session.execute(statement):
            entries.append(
                SitemapEntry(
                    path=f"/software/{row.slug}",
                    last_modified=row.updated_at,
                )
            )
            entries.append(
                SitemapEntry(
                    path=f"/software/{row.slug}/releases",
                    last_modified=row.updated_at,
                )
            )
        return tuple(entries)

    def get_category(self, slug: str) -> CatalogFacet | None:
        """Resolve one visible category without revealing hidden categories."""

        normalized = slug.strip().casefold()
        statement = select(Category).where(
            Category.slug == normalized,
            Category.is_visible.is_(True),
        )
        category = self.session.scalar(statement)
        if category is None:
            return None
        public_count = self.session.scalar(
            select(func.count(Software.id)).where(
                Software.category_id == category.id,
                Software.status == SoftwareStatus.PUBLISHED,
                Software.visibility == Visibility.PUBLIC,
            )
        )
        return CatalogFacet(
            name=category.name,
            slug=category.slug,
            description=category.description,
            software_count=int(public_count or 0),
        )

    def get_tag(self, slug: str) -> CatalogFacet | None:
        """Resolve a tag only when it is attached to public software."""

        normalized = slug.strip().casefold()
        count = func.count(func.distinct(Software.id))
        statement = (
            select(Tag.name, Tag.slug, count.label("software_count"))
            .join(software_tags, software_tags.c.tag_id == Tag.id)
            .join(Software, Software.id == software_tags.c.software_id)
            .where(
                Tag.slug == normalized,
                Software.status == SoftwareStatus.PUBLISHED,
                Software.visibility == Visibility.PUBLIC,
            )
            .group_by(Tag.id, Tag.name, Tag.slug)
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return CatalogFacet(
            name=row.name,
            slug=row.slug,
            description=None,
            software_count=int(row.software_count),
        )
