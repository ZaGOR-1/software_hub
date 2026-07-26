"""Unit tests for bounded pagination schemas."""

import pytest
from app.schemas.pagination import Page, Pagination


def test_pagination_defaults_and_offset() -> None:
    pagination = Pagination(page=3, per_page=25)

    assert pagination.offset == 50
    assert pagination.max_per_page == 100


@pytest.mark.parametrize(
    ("page", "per_page", "max_per_page", "message"),
    [
        (0, 20, 100, "Page"),
        (1, 0, 100, "Items per page"),
        (1, 20, 0, "Maximum"),
        (1, 101, 100, "must not exceed"),
    ],
)
def test_invalid_pagination_is_rejected(
    page: int,
    per_page: int,
    max_per_page: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        Pagination(page=page, per_page=per_page, max_per_page=max_per_page)


def test_page_metadata() -> None:
    page = Page(items=(1, 2), total=21, page=2, per_page=10)

    assert page.pages == 3
    assert page.has_previous is True
    assert page.has_next is True


def test_empty_page_has_zero_pages() -> None:
    page: Page[int] = Page(items=(), total=0, page=1, per_page=20)

    assert page.pages == 0
    assert page.has_previous is False
    assert page.has_next is False


@pytest.mark.parametrize(
    ("total", "page_number", "per_page"),
    [
        (-1, 1, 20),
        (0, 0, 20),
        (0, 1, 0),
    ],
)
def test_invalid_page_result_is_rejected(
    total: int,
    page_number: int,
    per_page: int,
) -> None:
    with pytest.raises(ValueError, match=r"negative|positive"):
        Page[object](items=(), total=total, page=page_number, per_page=per_page)
