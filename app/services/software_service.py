"""Software catalog application service and lifecycle orchestration."""

from collections.abc import Collection

from app.core.exceptions import EntityConflict, EntityNotFound, ValidationError
from app.core.time import utc_now
from app.database.session import Database
from app.models.category import Category
from app.models.enums import SoftwareStatus, Visibility
from app.models.software import Software
from app.models.tag import Tag
from app.repositories.category_repository import CategoryRepository
from app.repositories.software_repository import SoftwareFilters, SoftwareRepository
from app.repositories.tag_repository import TagRepository
from app.schemas.pagination import Page, Pagination
from app.services.audit_service import (
    AuditAction,
    AuditContext,
    append_context_audit_event,
)
from app.services.normalization import (
    normalize_http_url,
    normalize_name,
    normalize_optional_text,
    normalize_slug,
)
from app.services.policies import apply_software_transition


class SoftwareService:
    """Coordinate software reads and atomic domain mutations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _normalize_fields(  # noqa: PLR0913
        *,
        name: str,
        slug: str,
        short_description: str,
        full_description: str | None,
        developer_name: str | None,
        official_website_url: str | None,
        source_url: str | None,
        license_name: str | None,
        supported_os: str | None,
        system_requirements: str | None,
    ) -> dict[str, str | None]:
        try:
            normalized_name = normalize_name(name, max_length=180)
            normalized_slug = normalize_slug(slug, max_length=200, fallback=normalized_name)
            normalized_short = " ".join(short_description.split())
            if not normalized_short or len(normalized_short) > 500:
                raise ValueError("Short description must contain 1 to 500 characters.")
            return {
                "name": normalized_name,
                "slug": normalized_slug,
                "short_description": normalized_short,
                "full_description": normalize_optional_text(
                    full_description,
                    max_length=20_000,
                ),
                "developer_name": normalize_optional_text(developer_name, max_length=180),
                "official_website_url": normalize_http_url(official_website_url),
                "source_url": normalize_http_url(source_url),
                "license_name": normalize_optional_text(license_name, max_length=180),
                "supported_os": normalize_optional_text(supported_os, max_length=4_000),
                "system_requirements": normalize_optional_text(
                    system_requirements,
                    max_length=8_000,
                ),
            }
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    @staticmethod
    def _resolve_category_and_tags(
        *,
        category_id: int | None,
        tag_ids: Collection[int],
        category_repository: CategoryRepository,
        tag_repository: TagRepository,
    ) -> tuple[Category | None, list[Tag]]:
        category: Category | None = None
        if category_id is not None:
            category = category_repository.get(category_id)
            if category is None:
                raise EntityNotFound("Category not found.")
        unique_tag_ids = tuple(dict.fromkeys(tag_ids))
        tags = tag_repository.get_many(unique_tag_ids)
        if len(tags) != len(unique_tag_ids):
            raise EntityNotFound("One or more tags were not found.")
        return category, tags

    def create(  # noqa: PLR0913
        self,
        *,
        name: str,
        slug: str,
        short_description: str,
        full_description: str | None = None,
        developer_name: str | None = None,
        official_website_url: str | None = None,
        source_url: str | None = None,
        license_name: str | None = None,
        category_id: int | None = None,
        tag_ids: Collection[int] = (),
        supported_os: str | None = None,
        system_requirements: str | None = None,
        visibility: Visibility = Visibility.PRIVATE,
        is_featured: bool = False,
        audit: AuditContext | None = None,
    ) -> Software:
        """Create draft software and attach validated metadata references."""

        fields = self._normalize_fields(
            name=name,
            slug=slug,
            short_description=short_description,
            full_description=full_description,
            developer_name=developer_name,
            official_website_url=official_website_url,
            source_url=source_url,
            license_name=license_name,
            supported_os=supported_os,
            system_requirements=system_requirements,
        )
        with self.database.transaction() as session:
            software_repository = SoftwareRepository(session)
            if software_repository.get_by_slug(str(fields["slug"])) is not None:
                raise EntityConflict("Software with this slug already exists.")
            category, tags = self._resolve_category_and_tags(
                category_id=category_id,
                tag_ids=tag_ids,
                category_repository=CategoryRepository(session),
                tag_repository=TagRepository(session),
            )
            software = software_repository.add(
                Software(
                    **fields,
                    category=category,
                    tags=tags,
                    status=SoftwareStatus.DRAFT,
                    visibility=visibility,
                    is_featured=is_featured,
                )
            )
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.SOFTWARE_CREATED,
                entity_type="software",
                entity_id=software.id,
                metadata={"slug": software.slug},
            )
            return software

    def get(self, software_id: int) -> Software:
        """Return software with its summary graph or raise a typed 404."""

        with self.database.session() as session:
            software = SoftwareRepository(session).get_with_graph(software_id)
            if software is None:
                raise EntityNotFound("Software not found.")
            return software

    def list(
        self,
        pagination: Pagination,
        filters: SoftwareFilters | None = None,
    ) -> Page[Software]:
        """Return a parameterized software search result."""

        try:
            with self.database.session() as session:
                return SoftwareRepository(session).list_page(pagination, filters)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def update(  # noqa: PLR0913
        self,
        software_id: int,
        *,
        name: str,
        slug: str,
        short_description: str,
        full_description: str | None,
        developer_name: str | None,
        official_website_url: str | None,
        source_url: str | None,
        license_name: str | None,
        category_id: int | None,
        tag_ids: Collection[int],
        supported_os: str | None,
        system_requirements: str | None,
        visibility: Visibility,
        is_featured: bool,
        audit: AuditContext | None = None,
    ) -> Software:
        """Replace editable software metadata without bypassing lifecycle rules."""

        fields = self._normalize_fields(
            name=name,
            slug=slug,
            short_description=short_description,
            full_description=full_description,
            developer_name=developer_name,
            official_website_url=official_website_url,
            source_url=source_url,
            license_name=license_name,
            supported_os=supported_os,
            system_requirements=system_requirements,
        )
        with self.database.transaction() as session:
            repository = SoftwareRepository(session)
            software = repository.get_with_graph(software_id)
            if software is None:
                raise EntityNotFound("Software not found.")
            conflict = repository.get_by_slug(str(fields["slug"]))
            if conflict is not None and conflict.id != software.id:
                raise EntityConflict("Software with this slug already exists.")
            category, tags = self._resolve_category_and_tags(
                category_id=category_id,
                tag_ids=tag_ids,
                category_repository=CategoryRepository(session),
                tag_repository=TagRepository(session),
            )
            for key, value in fields.items():
                setattr(software, key, value)
            software.category = category
            software.tags = tags
            software.visibility = visibility
            software.is_featured = is_featured
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.SOFTWARE_UPDATED,
                entity_type="software",
                entity_id=software.id,
                metadata={"slug": software.slug},
            )
            return software

    def replace_tags(
        self,
        software_id: int,
        tag_ids: Collection[int],
        *,
        audit: AuditContext | None = None,
    ) -> Software:
        """Replace all software tags in one transaction."""

        with self.database.transaction() as session:
            repository = SoftwareRepository(session)
            software = repository.get_with_graph(software_id)
            if software is None:
                raise EntityNotFound("Software not found.")
            tags = TagRepository(session).get_many(tag_ids)
            if len(tags) != len(set(tag_ids)):
                raise EntityNotFound("One or more tags were not found.")
            software.tags = tags
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.SOFTWARE_UPDATED,
                entity_type="software",
                entity_id=software.id,
                metadata={"changed": "tags"},
            )
            return software

    def transition_status(
        self,
        software_id: int,
        target: SoftwareStatus,
        *,
        audit: AuditContext | None = None,
    ) -> Software:
        """Apply one validated software status transition atomically."""

        with self.database.transaction() as session:
            repository = SoftwareRepository(session)
            software = repository.get(software_id)
            if software is None:
                raise EntityNotFound("Software not found.")
            previous = software.status
            apply_software_transition(software, target, now=utc_now())
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.SOFTWARE_STATUS_CHANGED,
                entity_type="software",
                entity_id=software.id,
                metadata={"from": previous.value, "to": target.value},
            )
            return software

    def set_visibility(
        self,
        software_id: int,
        visibility: Visibility,
        *,
        audit: AuditContext | None = None,
    ) -> Software:
        """Change software visibility without bypassing lifecycle state."""

        with self.database.transaction() as session:
            repository = SoftwareRepository(session)
            software = repository.get(software_id)
            if software is None:
                raise EntityNotFound("Software not found.")
            previous = software.visibility
            software.visibility = visibility
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.SOFTWARE_VISIBILITY_CHANGED,
                entity_type="software",
                entity_id=software.id,
                metadata={"from": previous.value, "to": visibility.value},
            )
            return software
