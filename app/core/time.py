"""Timezone-safe helpers for all application timestamps."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC and reject naive datetimes."""

    if value.tzinfo is None or value.utcoffset() is None:
        msg = "Naive datetimes are not allowed; provide timezone information."
        raise ValueError(msg)
    return value.astimezone(UTC)
