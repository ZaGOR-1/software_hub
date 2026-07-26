"""Tests for deterministic SQLAlchemy metadata conventions."""

from app.database.base import NAMING_CONVENTION, Base


def test_base_uses_deterministic_constraint_naming() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    assert NAMING_CONVENTION["pk"] == "pk_%(table_name)s"
    assert NAMING_CONVENTION["fk"].startswith("fk_")
