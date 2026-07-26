"""Content-Length guard coverage before multipart parsing."""

import pytest
from app.core.config import AppSettings
from app.core.constants import UPLOAD_REQUEST_OVERHEAD_BYTES
from app.core.exceptions import PayloadTooLarge, ValidationError
from app.routers.auth.dependencies import _validate_upload_content_length
from starlette.requests import Request


def _request(content_length: str | None) -> Request:
    headers = [] if content_length is None else [(b"content-length", content_length.encode())]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/admin/releases/1/files",
            "raw_path": b"/admin/releases/1/files",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 443),
        }
    )


def test_content_length_guard_allows_missing_and_bounded_values(
    test_settings: AppSettings,
) -> None:
    _validate_upload_content_length(_request(None), test_settings)
    _validate_upload_content_length(_request("123"), test_settings)


def test_content_length_guard_rejects_invalid_and_negative_values(
    test_settings: AppSettings,
) -> None:
    with pytest.raises(ValidationError):
        _validate_upload_content_length(_request("invalid"), test_settings)
    with pytest.raises(ValidationError):
        _validate_upload_content_length(_request("-1"), test_settings)


def test_content_length_guard_rejects_oversized_request(test_settings: AppSettings) -> None:
    oversized = test_settings.max_upload_size + UPLOAD_REQUEST_OVERHEAD_BYTES + 1
    with pytest.raises(PayloadTooLarge):
        _validate_upload_content_length(_request(str(oversized)), test_settings)
