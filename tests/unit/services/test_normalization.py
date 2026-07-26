"""Unit tests for application input normalization."""

import pytest
from app.services.normalization import normalize_name, normalize_slug


def test_name_whitespace_is_collapsed() -> None:
    assert normalize_name("  Seven   Zip  ", max_length=20) == "Seven Zip"


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_name_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_name(value, max_length=10)


def test_long_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="exceed"):
        normalize_name("abcdef", max_length=5)


def test_slug_is_normalized() -> None:
    assert normalize_slug("--Seven__Zip--", max_length=20) == "seven-zip"


@pytest.mark.parametrize("value", ["", "Програма", "bad slug", "bad%slug"])
def test_invalid_slug_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="Slug"):
        normalize_slug(value, max_length=50)


def test_long_slug_is_rejected() -> None:
    with pytest.raises(ValueError, match="exceed"):
        normalize_slug("valid-slug", max_length=5)
