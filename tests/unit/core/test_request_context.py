"""Tests for request-scoped correlation context."""

from app.core.request_context import bind_request_id, get_request_id, reset_request_id


def test_request_id_context_can_be_bound_and_reset() -> None:
    assert get_request_id() == "-"

    token = bind_request_id("request-123")
    assert get_request_id() == "request-123"

    reset_request_id(token)
    assert get_request_id("fallback") == "fallback"
