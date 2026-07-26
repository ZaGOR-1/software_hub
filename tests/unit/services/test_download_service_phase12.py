"""Pure response-header helpers for Phase 12 downloads."""

from app.services.download_service import build_content_disposition, safe_media_type


def test_content_disposition_supports_unicode_and_safe_fallback() -> None:
    header = build_content_disposition("Українська утиліта 1.0.zip")

    assert header.startswith('attachment; filename="')
    assert "filename*=UTF-8''" in header
    assert "%D0%A3" in header
    assert "\r" not in header
    assert "\n" not in header


def test_content_disposition_uses_bounded_download_fallback() -> None:
    header = build_content_disposition("Я" * 200 + ".exe")

    assert 'filename="download.exe"' in header
    assert "filename*=UTF-8''" in header


def test_safe_media_type_rejects_header_injection_and_parameters() -> None:
    assert safe_media_type("application/zip") == "application/zip"
    assert safe_media_type(" Application/X-7Z-Compressed ") == "application/x-7z-compressed"
    assert safe_media_type("text/plain\r\nX-Evil: yes") == "application/octet-stream"
    assert safe_media_type("application/zip; charset=utf-8") == "application/octet-stream"
