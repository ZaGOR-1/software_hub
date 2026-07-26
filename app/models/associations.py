"""Association tables for many-to-many domain relationships."""

from sqlalchemy import Column, ForeignKey, Table

from app.database.base import Base

software_tags = Table(
    "software_tags",
    Base.metadata,
    Column("software_id", ForeignKey("software.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)
