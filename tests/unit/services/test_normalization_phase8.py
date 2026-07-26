"""Phase 8 normalization and form validation coverage."""

import pytest
from app.schemas.admin_forms import SoftwareAdminForm, validation_messages
from app.services.normalization import (
    generate_slug,
    normalize_http_url,
    normalize_optional_text,
    normalize_slug,
)
from pydantic import ValidationError as PydanticValidationError


def test_slug_generation_transliterates_ukrainian_and_normalizes_ascii() -> None:
    assert generate_slug("Системні інструменти", max_length=140) == "systemni-instrumenty"
    assert normalize_slug("", max_length=140, fallback="Безпека") == "bezpeka"
    assert normalize_slug("Hello__World", max_length=140) == "hello-world"


def test_slug_generation_rejects_empty_and_invalid_values() -> None:
    with pytest.raises(ValueError, match="could not be generated"):
        generate_slug("😀", max_length=140)
    with pytest.raises(ValueError, match="lowercase ASCII"):
        normalize_slug("bad/value", max_length=140)
    with pytest.raises(ValueError, match="must not exceed"):
        normalize_slug("a" * 141, max_length=140)


def test_optional_text_and_http_url_validation() -> None:
    assert normalize_optional_text("  hello\nworld  ", max_length=20) == "hello\nworld"
    assert normalize_optional_text("   ", max_length=20) is None
    assert normalize_http_url(" https://example.com/path?q=1 ") == "https://example.com/path?q=1"
    assert normalize_http_url("") is None
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        normalize_http_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="credentials"):
        normalize_http_url("https://user:pass@example.com")
    with pytest.raises(ValueError, match="forbidden"):
        normalize_http_url("https://example.com/\nheader")
    with pytest.raises(ValueError, match="must not exceed"):
        normalize_optional_text("x" * 21, max_length=20)


def test_software_form_normalizes_multivalue_fields_and_safe_errors() -> None:
    form = SoftwareAdminForm.model_validate(
        {
            "name": "Tool",
            "slug": "",
            "short_description": "Description",
            "category_id": "",
            "tag_ids": ["1", "2"],
            "visibility": "public",
            "is_featured": "on",
        }
    )
    assert form.category_id is None
    assert form.tag_ids == (1, 2)
    assert form.is_featured is True

    with pytest.raises(PydanticValidationError) as captured:
        SoftwareAdminForm.model_validate({"name": "", "short_description": "", "tag_ids": "bad"})
    messages = validation_messages(captured.value)
    assert messages
    assert "bad" not in " ".join(messages)
