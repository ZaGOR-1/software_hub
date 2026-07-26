"""Reusable SQLAlchemy domain column types."""

from enum import StrEnum

from sqlalchemy import Enum as SQLAlchemyEnum


def enum_type[EnumT: StrEnum](enum_class: type[EnumT], *, name: str) -> SQLAlchemyEnum:
    """Store enum values as portable validated strings rather than member names."""

    return SQLAlchemyEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
        length=max(len(member.value) for member in enum_class),
    )
