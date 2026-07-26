"""Structured logging and redaction tests."""

import json
import logging

from app.core.config import AppSettings
from app.core.constants import REDACTED_VALUE
from app.core.logging import JsonFormatter, PlainFormatter, configure_logging, redact_sensitive_data
from app.core.request_context import bind_request_id, reset_request_id


def test_redaction_recurses_through_structured_data() -> None:
    value = {
        "username": "denis",
        "password": "hidden",
        "headers": {
            "Authorization": "Bearer secret",
            "X-Request-ID": "safe",
        },
        "items": [{"csrf_token": "token"}, "plain"],
        "roles": {"admin", "editor"},
    }

    redacted = redact_sensitive_data(value)

    assert redacted["username"] == "denis"
    assert redacted["password"] == REDACTED_VALUE
    assert redacted["headers"]["Authorization"] == REDACTED_VALUE
    assert redacted["headers"]["X-Request-ID"] == "safe"
    assert redacted["items"][0]["csrf_token"] == REDACTED_VALUE
    assert redacted["roles"] == ["admin", "editor"]


def test_redaction_uses_repr_for_unknown_objects() -> None:
    marker = object()

    assert redact_sensitive_data(marker).startswith("<object object at")


def test_json_formatter_adds_context_and_redacts_extras() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="software-hub.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="event_name",
        args=(),
        exc_info=None,
    )
    record.password = "secret"
    record.metadata = {"session_cookie": "secret", "safe": 7}
    token = bind_request_id("req-json")
    try:
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_id(token)

    assert payload["event"] == "event_name"
    assert payload["request_id"] == "req-json"
    assert payload["password"] == REDACTED_VALUE
    assert payload["metadata"] == {"session_cookie": REDACTED_VALUE, "safe": 7}


def test_json_formatter_serializes_exception_information() -> None:
    formatter = JsonFormatter()
    try:
        raise RuntimeError("formatter-test")
    except RuntimeError:
        record = logging.LogRecord(
            name="software-hub.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    payload = json.loads(formatter.format(record))
    assert "RuntimeError: formatter-test" in payload["exception"]


def test_plain_formatter_injects_request_id() -> None:
    formatter = PlainFormatter("%(request_id)s %(message)s")
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)

    assert formatter.format(record) == "- hello"


def test_configure_logging_supports_json_and_plain_modes() -> None:
    configure_logging(AppSettings(_env_file=None, log_json=True))
    assert logging.getLogger().handlers[0].formatter.__class__ is JsonFormatter

    configure_logging(AppSettings(_env_file=None, log_json=False))
    assert logging.getLogger().handlers[0].formatter.__class__ is PlainFormatter
