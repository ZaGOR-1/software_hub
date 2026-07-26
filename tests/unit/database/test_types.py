"""Tests for portable custom SQLAlchemy types."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.database.types import UTCDateTime
from sqlalchemy.dialects import sqlite


def test_utc_datetime_accepts_none() -> None:
    column_type = UTCDateTime()
    dialect = sqlite.dialect()

    assert column_type.process_bind_param(None, dialect) is None
    assert column_type.process_result_value(None, dialect) is None


def test_utc_datetime_normalizes_aware_value_to_naive_utc_for_storage() -> None:
    column_type = UTCDateTime()
    dialect = sqlite.dialect()
    source = datetime(2026, 7, 23, 18, 30, tzinfo=timezone(timedelta(hours=3)))

    stored = column_type.process_bind_param(source, dialect)

    assert stored == datetime(2026, 7, 23, 15, 30)
    assert stored is not None
    assert stored.tzinfo is None


def test_utc_datetime_rejects_naive_input() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        UTCDateTime().process_bind_param(datetime(2026, 7, 23, 15, 30), sqlite.dialect())


def test_utc_datetime_restores_naive_database_value_as_utc() -> None:
    restored = UTCDateTime().process_result_value(
        datetime(2026, 7, 23, 15, 30),
        sqlite.dialect(),
    )

    assert restored == datetime(2026, 7, 23, 15, 30, tzinfo=UTC)


def test_utc_datetime_converts_aware_result_to_utc() -> None:
    source = datetime(2026, 7, 23, 18, 30, tzinfo=timezone(timedelta(hours=3)))

    restored = UTCDateTime().process_result_value(source, sqlite.dialect())

    assert restored == datetime(2026, 7, 23, 15, 30, tzinfo=UTC)
