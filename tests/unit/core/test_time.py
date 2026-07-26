"""Tests for UTC-only timestamp helpers."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.core.time import ensure_utc, utc_now


def test_utc_now_is_timezone_aware() -> None:
    value = utc_now()

    assert value.tzinfo is UTC
    assert value.utcoffset() == timedelta(0)


def test_ensure_utc_converts_aware_datetime() -> None:
    source = datetime(2026, 7, 23, 18, 0, tzinfo=timezone(timedelta(hours=3)))

    assert ensure_utc(source) == datetime(2026, 7, 23, 15, 0, tzinfo=UTC)


def test_ensure_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="Naive datetimes"):
        ensure_utc(datetime(2026, 7, 23, 15, 0))
