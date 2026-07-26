"""Validated pagination values and immutable page results."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import TypeVar

ItemT = TypeVar("ItemT")


@dataclass(frozen=True, slots=True)
class Pagination:
    """One-based pagination request with a defensive per-page ceiling."""

    page: int = 1
    per_page: int = 20
    max_per_page: int = 100

    def __post_init__(self) -> None:
        if self.page < 1:
            msg = "Page must be at least 1."
            raise ValueError(msg)
        if self.per_page < 1:
            msg = "Items per page must be at least 1."
            raise ValueError(msg)
        if self.max_per_page < 1:
            msg = "Maximum items per page must be at least 1."
            raise ValueError(msg)
        if self.per_page > self.max_per_page:
            msg = f"Items per page must not exceed {self.max_per_page}."
            raise ValueError(msg)

    @property
    def offset(self) -> int:
        """Return the SQL offset for the requested page."""

        return (self.page - 1) * self.per_page


@dataclass(frozen=True, slots=True)
class Page[ItemT]:
    """Immutable page result returned by repositories and services."""

    items: Sequence[ItemT]
    total: int
    page: int
    per_page: int

    def __post_init__(self) -> None:
        if self.total < 0:
            msg = "Total item count cannot be negative."
            raise ValueError(msg)
        if self.page < 1 or self.per_page < 1:
            msg = "Page and items per page must be positive."
            raise ValueError(msg)

    @property
    def pages(self) -> int:
        """Return the total page count; an empty result has zero pages."""

        if self.total == 0:
            return 0
        return ceil(self.total / self.per_page)

    @property
    def has_previous(self) -> bool:
        """Return whether a previous page exists."""

        return self.page > 1 and self.pages > 0

    @property
    def has_next(self) -> bool:
        """Return whether a later page exists."""

        return self.page < self.pages
