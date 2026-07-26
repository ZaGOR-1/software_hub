"""Transaction-oriented category application service."""

from app.core.exceptions import EntityConflict, EntityNotFound, ValidationError
from app.database.session import Database
from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.pagination import Page, Pagination
from app.services.audit_service import (
    AuditAction,
    AuditContext,
    append_context_audit_event,
)
from app.services.normalization import (
    normalize_name,
    normalize_optional_text,
    normalize_slug,
)


class CategoryService:
    """Coordinate category reads and writes through short transactions."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        name: str,
        slug: str,
        description: str | None = None,
        sort_order: int = 0,
        is_visible: bool = True,
        audit: AuditContext | None = None,
    ) -> Category:
        """Create a unique category and optionally append an audit event."""

        try:
            normalized_name = normalize_name(name, max_length=120)
            normalized_slug = normalize_slug(slug, max_length=140, fallback=normalized_name)
            normalized_description = normalize_optional_text(description, max_length=2_000)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if sort_order < 0:
            raise ValidationError("Category sort order cannot be negative.")
        with self.database.transaction() as session:
            repository = CategoryRepository(session)
            if repository.get_by_slug(normalized_slug) is not None:
                raise EntityConflict("A category with this slug already exists.")
            category = repository.add(
                Category(
                    name=normalized_name,
                    slug=normalized_slug,
                    description=normalized_description,
                    sort_order=sort_order,
                    is_visible=is_visible,
                )
            )
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.CATEGORY_CREATED,
                entity_type="category",
                entity_id=category.id,
                metadata={"slug": category.slug},
            )
            return category

    def get(self, category_id: int) -> Category:
        """Return one category or raise a typed 404."""

        with self.database.session() as session:
            category = CategoryRepository(session).get(category_id)
            if category is None:
                raise EntityNotFound("Category not found.")
            return category

    def update(
        self,
        category_id: int,
        *,
        name: str,
        slug: str,
        description: str | None,
        sort_order: int,
        is_visible: bool,
        audit: AuditContext | None = None,
    ) -> Category:
        """Replace editable category metadata."""

        try:
            normalized_name = normalize_name(name, max_length=120)
            normalized_slug = normalize_slug(slug, max_length=140, fallback=normalized_name)
            normalized_description = normalize_optional_text(description, max_length=2_000)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if sort_order < 0:
            raise ValidationError("Category sort order cannot be negative.")
        with self.database.transaction() as session:
            repository = CategoryRepository(session)
            category = repository.get(category_id)
            if category is None:
                raise EntityNotFound("Category not found.")
            conflict = repository.get_by_slug(normalized_slug)
            if conflict is not None and conflict.id != category.id:
                raise EntityConflict("A category with this slug already exists.")
            category.name = normalized_name
            category.slug = normalized_slug
            category.description = normalized_description
            category.sort_order = sort_order
            category.is_visible = is_visible
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.CATEGORY_UPDATED,
                entity_type="category",
                entity_id=category.id,
                metadata={"slug": category.slug},
            )
            return category

    def delete(self, category_id: int, *, audit: AuditContext | None = None) -> None:
        """Delete category metadata; linked software keeps a null category."""

        with self.database.transaction() as session:
            repository = CategoryRepository(session)
            category = repository.get(category_id)
            if category is None:
                raise EntityNotFound("Category not found.")
            slug = category.slug
            repository.delete(category)
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.CATEGORY_DELETED,
                entity_type="category",
                entity_id=category_id,
                metadata={"slug": slug},
            )

    def list(self, pagination: Pagination, *, visible_only: bool = False) -> Page[Category]:
        """Read one category page without starting a write transaction."""

        with self.database.session() as session:
            return CategoryRepository(session).list_page(
                pagination,
                visible_only=visible_only,
            )
