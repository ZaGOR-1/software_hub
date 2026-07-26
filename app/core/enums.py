"""Shared string enumerations used by configuration and the application core."""

from enum import StrEnum


class AppEnvironment(StrEnum):
    """Supported application execution environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported standard-library logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SQLiteSynchronousMode(StrEnum):
    """Supported SQLite durability/performance trade-offs."""

    OFF = "OFF"
    NORMAL = "NORMAL"
    FULL = "FULL"
    EXTRA = "EXTRA"
