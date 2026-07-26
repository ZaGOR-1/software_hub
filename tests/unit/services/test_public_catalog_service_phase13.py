"""Small pure helper coverage for public catalog presentation rules."""

from app.services.public_catalog_service import _format_bytes, _initials


def test_public_size_formatting_uses_binary_units() -> None:
    assert _format_bytes(999) == "999 Б"
    assert _format_bytes(1024) == "1.0 КіБ"
    assert _format_bytes(1024 * 1024) == "1.0 МіБ"
    assert _format_bytes(1024**3) == "1.0 ГіБ"
    assert _format_bytes(1024**4) == "1.0 ТіБ"


def test_public_initials_are_deterministic() -> None:
    assert _initials("7-Zip") == "7Z"
    assert _initials("RustDesk Client") == "RC"
    assert _initials("A") == "A"
    assert _initials("   ") == "SH"
