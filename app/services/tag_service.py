"""Transaction-oriented tag application service."""

from app.core.exceptions import EntityConflict, EntityNotFound, ValidationError
from app.database.session import Database
from app.models.tag import Tag
from app.repositories.tag_repository import TagRepository
from app.schemas.pagination import Page, Pagination
from app.services.audit_service import (
    AuditAction,
    AuditContext,
    append_context_audit_event,
)
from app.services.normalization import normalize_name, normalize_slug


class TagService:
    """Coordinate tag reads and writes through short transactions."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        name: str,
        slug: str,
        audit: AuditContext | None = None,
    ) -> Tag:
        """Create one unique tag."""

        try:
            normalized_name = normalize_name(name, max_length=120)
            normalized_slug = normalize_slug(slug, max_length=140, fallback=normalized_name)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        with self.database.transaction() as session:
            repository = TagRepository(session)
            if repository.get_by_slug(normalized_slug) is not None:
                raise EntityConflict("A tag with this slug already exists.")
            tag = repository.add(Tag(name=normalized_name, slug=normalized_slug))
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.TAG_CREATED,
                entity_type="tag",
                entity_id=tag.id,
                metadata={"slug": tag.slug},
            )
            return tag

    def get(self, tag_id: int) -> Tag:
        """Return one tag or raise a typed 404."""

        with self.database.session() as session:
            tag = TagRepository(session).get(tag_id)
            if tag is None:
                raise EntityNotFound("Tag not found.")
            return tag

    def update(
        self,
        tag_id: int,
        *,
        name: str,
        slug: str,
        audit: AuditContext | None = None,
    ) -> Tag:
        """Replace editable tag metadata."""

        try:
            normalized_name = normalize_name(name, max_length=120)
            normalized_slug = normalize_slug(slug, max_length=140, fallback=normalized_name)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        with self.database.transaction() as session:
            repository = TagRepository(session)
            tag = repository.get(tag_id)
            if tag is None:
                raise EntityNotFound("Tag not found.")
            conflict = repository.get_by_slug(normalized_slug)
            if conflict is not None and conflict.id != tag.id:
                raise EntityConflict("A tag with this slug already exists.")
            tag.name = normalized_name
            tag.slug = normalized_slug
            session.flush()
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.TAG_UPDATED,
                entity_type="tag",
                entity_id=tag.id,
                metadata={"slug": tag.slug},
            )
            return tag

    def delete(self, tag_id: int, *, audit: AuditContext | None = None) -> None:
        """Delete tag metadata and its association rows."""

        with self.database.transaction() as session:
            repository = TagRepository(session)
            tag = repository.get(tag_id)
            if tag is None:
                raise EntityNotFound("Tag not found.")
            slug = tag.slug
            repository.delete(tag)
            append_context_audit_event(
                session,
                context=audit,
                action=AuditAction.TAG_DELETED,
                entity_type="tag",
                entity_id=tag_id,
                metadata={"slug": slug},
            )

    def list(self, pagination: Pagination) -> Page[Tag]:
        """Read one tag page."""

        with self.database.session() as session:
            return TagRepository(session).list_page(pagination)
