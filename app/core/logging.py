"""Structured logging with request correlation and defensive redaction."""

import json
import logging
import logging.config
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.config import AppSettings
from app.core.constants import REDACTED_VALUE, SENSITIVE_KEY_FRAGMENTS
from app.core.request_context import get_request_id

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)


def is_sensitive_key(key: str) -> bool:
    """Return whether a structured field name may contain a secret."""

    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact values stored under security-sensitive field names."""

    if key is not None and is_sensitive_key(key):
        return REDACTED_VALUE
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_sensitive_data(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, set | frozenset):
        items = [redact_sensitive_data(item) for item in value]
        return sorted(items, key=repr)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)


class JsonFormatter(logging.Formatter):
    """Render one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            if key in {"message", "asctime", "request_id"}:
                continue
            payload[key] = redact_sensitive_data(value, key=key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


class PlainFormatter(logging.Formatter):
    """Readable development formatter that still includes the request ID."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return super().format(record)


def configure_logging(settings: AppSettings) -> None:
    """Configure root and server loggers without exposing application settings."""

    formatter_name = "json" if settings.log_json else "plain"
    configuration: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "app.core.logging.JsonFormatter"},
            "plain": {
                "()": "app.core.logging.PlainFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
            },
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "stream": "ext://sys.stdout",
            }
        },
        "root": {
            "handlers": ["stdout"],
            "level": settings.log_level.value,
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["stdout"],
                "level": settings.log_level.value,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["stdout"],
                "level": settings.log_level.value,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["stdout"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(configuration)

    # Ensure no accidental fallback handler writes differently formatted records.
    logging.lastResort = logging.StreamHandler(sys.stderr)
