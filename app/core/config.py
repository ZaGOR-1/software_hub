"""Typed, fail-fast application settings."""

import re
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app import __version__
from app.core.constants import (
    CSRF_TOKEN_MAX_LENGTH,
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_ARGON2_MEMORY_COST_KIB,
    DEFAULT_ARGON2_PARALLELISM,
    DEFAULT_ARGON2_TIME_COST,
    DEFAULT_BACKUP_MIN_FREE_BYTES,
    DEFAULT_BACKUP_RETENTION_COUNT,
    DEFAULT_CLAMAV_TIMEOUT_SECONDS,
    DEFAULT_CONTENT_SECURITY_POLICY,
    DEFAULT_CSRF_TOKEN_TTL_SECONDS,
    DEFAULT_LOGIN_CSRF_TTL_SECONDS,
    DEFAULT_LOGIN_LOCKOUT_SECONDS,
    DEFAULT_LOGIN_MAX_FAILED_ATTEMPTS,
    DEFAULT_MAX_UPLOAD_SIZE,
    DEFAULT_PASSWORD_MAX_LENGTH,
    DEFAULT_PASSWORD_MIN_LENGTH,
    DEFAULT_SESSION_ABSOLUTE_TIMEOUT_SECONDS,
    DEFAULT_SESSION_IDLE_TIMEOUT_SECONDS,
    DEFAULT_SESSION_TOUCH_INTERVAL_SECONDS,
    DEFAULT_SQLITE_BUSY_TIMEOUT_MS,
    DEFAULT_STORAGE_MIN_FREE_BYTES,
    DEFAULT_TEMPORARY_FILE_MAX_AGE_SECONDS,
    DEFAULT_TRUSTED_HOSTS,
    DEFAULT_TRUSTED_PROXY_NETWORKS,
    DEFAULT_UPLOAD_CHUNK_SIZE,
    DEFAULT_UPLOAD_MAGIC_SAMPLE_SIZE,
    MAXIMUM_BACKUP_RETENTION_COUNT,
    MAXIMUM_SQLITE_BUSY_TIMEOUT_MS,
    MAXIMUM_STORAGE_MIN_FREE_BYTES,
    MAXIMUM_TEMPORARY_FILE_MAX_AGE_SECONDS,
    MAXIMUM_UPLOAD_CHUNK_SIZE,
    MAXIMUM_UPLOAD_MAGIC_SAMPLE_SIZE,
    MAXIMUM_UPLOAD_SIZE,
    MINIMUM_SECRET_LENGTH,
    MINIMUM_SQLITE_BUSY_TIMEOUT_MS,
    MINIMUM_TEMPORARY_FILE_MAX_AGE_SECONDS,
    MINIMUM_UPLOAD_CHUNK_SIZE,
    MINIMUM_UPLOAD_SIZE,
    REQUEST_ID_HEADER,
    REQUEST_ID_MAX_LENGTH,
    SESSION_COOKIE_NAME_PATTERN,
)
from app.core.enums import AppEnvironment, LogLevel, SQLiteSynchronousMode

_HOST_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
_EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]{1,15}$")
_HEADER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
_COMMON_WEAK_SECRETS = frozenset(
    {
        "changeme",
        "change-me",
        "default",
        "password",
        "secret",
        "software-hub",
        "softwarehub",
    }
)


def _split_csv(value: Any) -> Any:
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    return value


def _validate_secret(secret: SecretStr | None, field_name: str) -> None:
    if secret is None:
        return
    raw_value = secret.get_secret_value()
    normalized = raw_value.strip().lower()
    if len(raw_value) < MINIMUM_SECRET_LENGTH:
        msg = f"{field_name} must contain at least {MINIMUM_SECRET_LENGTH} characters."
        raise ValueError(msg)
    if normalized in _COMMON_WEAK_SECRETS or len(set(raw_value)) < 8:
        msg = f"{field_name} is too predictable."
        raise ValueError(msg)


def _validate_host(host: str) -> str:
    normalized = host.strip().lower()
    if not normalized:
        raise ValueError("Trusted hosts cannot contain empty values.")
    if "://" in normalized or "/" in normalized or any(char.isspace() for char in normalized):
        raise ValueError(f"Invalid trusted host: {host!r}.")
    if normalized == "*":
        return normalized
    candidate = normalized[2:] if normalized.startswith("*.") else normalized
    if "*" in candidate or not _HOST_LABEL_PATTERN.fullmatch(candidate):
        raise ValueError(f"Invalid trusted host: {host!r}.")
    return normalized


class AppSettings(BaseSettings):
    """Validated runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SOFTWARE_HUB_",
        extra="ignore",
        case_sensitive=False,
        frozen=True,
        validate_default=True,
        enable_decoding=False,
    )

    app_name: str = "Software Hub"
    app_version: str = __version__
    app_environment: AppEnvironment = AppEnvironment.DEVELOPMENT
    app_debug: bool = False
    docs_enabled: bool = True

    app_secret_key: SecretStr | None = None
    csrf_secret: SecretStr | None = None
    csrf_form_field_name: str = Field(
        default="csrf_token",
        pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$",
    )
    csrf_header_name: str = "X-CSRF-Token"
    csrf_token_ttl_seconds: int = Field(default=DEFAULT_CSRF_TOKEN_TTL_SECONDS, ge=300, le=43_200)
    csrf_token_max_length: int = Field(default=CSRF_TOKEN_MAX_LENGTH, ge=128, le=2_048)
    login_csrf_cookie_name: str = Field(
        default="software_hub_login_csrf",
        pattern=SESSION_COOKIE_NAME_PATTERN,
    )
    login_csrf_cookie_path: str = Field(
        default="/admin/login",
        pattern=r"^/[A-Za-z0-9/_-]*$",
    )
    login_csrf_cookie_same_site: Literal["lax", "strict"] = "strict"
    login_csrf_ttl_seconds: int = Field(default=DEFAULT_LOGIN_CSRF_TTL_SECONDS, ge=60, le=3_600)

    session_cookie_name: str = Field(
        default="software_hub_session",
        pattern=SESSION_COOKIE_NAME_PATTERN,
    )
    session_cookie_path: str = Field(default="/", pattern=r"^/[A-Za-z0-9/_-]*$")
    session_cookie_same_site: Literal["lax", "strict"] = "lax"
    session_cookie_secure: bool | None = None
    session_idle_timeout_seconds: int = Field(
        default=DEFAULT_SESSION_IDLE_TIMEOUT_SECONDS, ge=60, le=86_400
    )
    session_absolute_timeout_seconds: int = Field(
        default=DEFAULT_SESSION_ABSOLUTE_TIMEOUT_SECONDS, ge=300, le=604_800
    )
    session_touch_interval_seconds: int = Field(
        default=DEFAULT_SESSION_TOUCH_INTERVAL_SECONDS, ge=0, le=3_600
    )
    login_max_failed_attempts: int = Field(default=DEFAULT_LOGIN_MAX_FAILED_ATTEMPTS, ge=2, le=20)
    login_lockout_seconds: int = Field(default=DEFAULT_LOGIN_LOCKOUT_SECONDS, ge=60, le=86_400)
    password_min_length: int = Field(default=DEFAULT_PASSWORD_MIN_LENGTH, ge=8, le=128)
    password_max_length: int = Field(default=DEFAULT_PASSWORD_MAX_LENGTH, ge=64, le=4_096)
    argon2_time_cost: int = Field(default=DEFAULT_ARGON2_TIME_COST, ge=1, le=10)
    argon2_memory_cost_kib: int = Field(
        default=DEFAULT_ARGON2_MEMORY_COST_KIB, ge=1_024, le=1_048_576
    )
    argon2_parallelism: int = Field(default=DEFAULT_ARGON2_PARALLELISM, ge=1, le=16)

    database_url: str = "sqlite+pysqlite:////srv/software-hub/database/software-hub.db"
    database_echo: bool = False
    sqlite_busy_timeout_ms: int = Field(
        default=DEFAULT_SQLITE_BUSY_TIMEOUT_MS,
        ge=MINIMUM_SQLITE_BUSY_TIMEOUT_MS,
        le=MAXIMUM_SQLITE_BUSY_TIMEOUT_MS,
    )
    sqlite_synchronous_mode: SQLiteSynchronousMode = SQLiteSynchronousMode.NORMAL

    public_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    internal_download_prefix: str = Field(
        default="/protected-downloads/",
        pattern=r"^/[A-Za-z0-9/_-]+/$",
    )
    trusted_hosts: tuple[str, ...] = DEFAULT_TRUSTED_HOSTS
    trusted_proxy_networks: tuple[str, ...] = DEFAULT_TRUSTED_PROXY_NETWORKS

    storage_root: Path = Path("/srv/software-hub/storage")
    temporary_root: Path = Path("/srv/software-hub/storage/temporary")
    quarantine_root: Path = Path("/srv/software-hub/storage/quarantine")
    icons_root: Path = Path("/srv/software-hub/storage/icons")
    backup_root: Path = Path("/srv/software-hub/backups")
    backup_retention_count: int = Field(
        default=DEFAULT_BACKUP_RETENTION_COUNT,
        ge=1,
        le=MAXIMUM_BACKUP_RETENTION_COUNT,
    )
    backup_min_free_bytes: int = Field(
        default=DEFAULT_BACKUP_MIN_FREE_BYTES,
        ge=0,
        le=MAXIMUM_STORAGE_MIN_FREE_BYTES,
    )
    storage_min_free_bytes: int = Field(
        default=DEFAULT_STORAGE_MIN_FREE_BYTES,
        ge=0,
        le=MAXIMUM_STORAGE_MIN_FREE_BYTES,
    )
    temporary_file_max_age_seconds: int = Field(
        default=DEFAULT_TEMPORARY_FILE_MAX_AGE_SECONDS,
        ge=MINIMUM_TEMPORARY_FILE_MAX_AGE_SECONDS,
        le=MAXIMUM_TEMPORARY_FILE_MAX_AGE_SECONDS,
    )

    max_upload_size: int = Field(
        default=DEFAULT_MAX_UPLOAD_SIZE,
        ge=MINIMUM_UPLOAD_SIZE,
        le=MAXIMUM_UPLOAD_SIZE,
    )
    upload_chunk_size: int = Field(
        default=DEFAULT_UPLOAD_CHUNK_SIZE,
        ge=MINIMUM_UPLOAD_CHUNK_SIZE,
        le=MAXIMUM_UPLOAD_CHUNK_SIZE,
    )
    upload_magic_sample_size: int = Field(
        default=DEFAULT_UPLOAD_MAGIC_SAMPLE_SIZE,
        ge=64,
        le=MAXIMUM_UPLOAD_MAGIC_SAMPLE_SIZE,
    )
    allowed_extensions: tuple[str, ...] = DEFAULT_ALLOWED_EXTENSIONS
    clamav_enabled: bool = False
    clamav_command: str = "clamscan"
    clamav_timeout_seconds: int = Field(
        default=DEFAULT_CLAMAV_TIMEOUT_SECONDS,
        ge=5,
        le=3_600,
    )

    log_level: LogLevel = LogLevel.INFO
    log_json: bool = True
    request_id_header: str = REQUEST_ID_HEADER
    request_id_max_length: int = Field(
        default=REQUEST_ID_MAX_LENGTH, ge=32, le=REQUEST_ID_MAX_LENGTH
    )

    security_headers_enabled: bool = True
    content_security_policy: str = DEFAULT_CONTENT_SECURITY_POLICY
    health_path: str = Field(default="/health", pattern=r"^/[a-z0-9/_-]*$")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        candidate = value.strip()
        try:
            url = make_url(candidate)
        except ArgumentError as exc:
            raise ValueError("database_url must be a valid SQLAlchemy URL.") from exc
        if url.get_backend_name() != "sqlite":
            raise ValueError("SQLite is the only supported database backend for the MVP.")
        if url.database is None or not url.database.strip():
            raise ValueError("database_url must identify a SQLite database.")
        return candidate

    @field_validator("trusted_hosts", "trusted_proxy_networks", "allowed_extensions", mode="before")
    @classmethod
    def parse_comma_separated_values(cls, value: Any) -> Any:
        """Accept convenient comma-separated environment variable values."""

        return _split_csv(value)

    @field_validator("trusted_hosts")
    @classmethod
    def validate_trusted_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("At least one trusted host is required.")
        normalized = tuple(dict.fromkeys(_validate_host(host) for host in value))
        return normalized

    @field_validator("trusted_proxy_networks")
    @classmethod
    def validate_trusted_proxy_networks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for network in value:
            try:
                normalized.append(str(ip_network(network, strict=False)))
            except ValueError as exc:
                raise ValueError(f"Invalid trusted proxy network: {network!r}.") from exc
        return tuple(dict.fromkeys(normalized))

    @field_validator("allowed_extensions")
    @classmethod
    def validate_allowed_extensions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("At least one upload extension must be allowed.")
        normalized: list[str] = []
        for extension in value:
            candidate = extension.strip().lower()
            if not candidate.startswith("."):
                candidate = f".{candidate}"
            if not _EXTENSION_PATTERN.fullmatch(candidate):
                raise ValueError(f"Invalid file extension: {extension!r}.")
            normalized.append(candidate)
        return tuple(dict.fromkeys(normalized))

    @field_validator(
        "storage_root",
        "temporary_root",
        "quarantine_root",
        "icons_root",
        "backup_root",
    )
    @classmethod
    def validate_absolute_paths(cls, value: Path) -> Path:
        expanded = value.expanduser()
        if not expanded.is_absolute():
            raise ValueError(f"Configured path must be absolute: {value!s}.")
        return expanded

    @field_validator("request_id_header", "csrf_header_name")
    @classmethod
    def validate_header_name(cls, value: str) -> str:
        if not _HEADER_NAME_PATTERN.fullmatch(value):
            raise ValueError("Configured value must be a valid HTTP header name.")
        return value

    @field_validator("clamav_command")
    @classmethod
    def validate_clamav_command(cls, value: str) -> str:
        candidate = value.strip()
        if (
            not candidate
            or any(character in candidate for character in ("\x00", "\r", "\n"))
            or any(character.isspace() for character in candidate)
        ):
            raise ValueError("clamav_command must be one executable name or path.")
        return candidate

    @field_validator("content_security_policy")
    @classmethod
    def prevent_header_injection(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("Content Security Policy cannot contain line breaks.")
        return value.strip()

    @model_validator(mode="after")
    def validate_security_invariants(self) -> AppSettings:  # noqa: PLR0912
        _validate_secret(self.app_secret_key, "app_secret_key")
        _validate_secret(self.csrf_secret, "csrf_secret")

        if (
            self.app_secret_key is not None
            and self.csrf_secret is not None
            and self.app_secret_key.get_secret_value() == self.csrf_secret.get_secret_value()
        ):
            raise ValueError("app_secret_key and csrf_secret must be different.")

        if self.session_absolute_timeout_seconds <= self.session_idle_timeout_seconds:
            raise ValueError("Absolute session lifetime must be longer than the idle timeout.")
        if self.session_touch_interval_seconds >= self.session_idle_timeout_seconds:
            raise ValueError("Session touch interval must be shorter than the idle timeout.")
        if self.password_max_length <= self.password_min_length:
            raise ValueError("password_max_length must exceed password_min_length.")
        if self.csrf_token_ttl_seconds > self.session_absolute_timeout_seconds:
            raise ValueError("CSRF token lifetime cannot exceed the absolute session lifetime.")
        if self.login_csrf_cookie_name == self.session_cookie_name:
            raise ValueError("Login CSRF and session cookies must use different names.")
        if self.session_cookie_path != "/":
            raise ValueError("The session cookie path must cover public download authorization.")
        if self.internal_download_prefix in {"/", "/admin/", "/download/", "/static/"}:
            raise ValueError("internal_download_prefix must use a dedicated internal path.")

        storage_root = self.storage_root.resolve(strict=False)
        managed_storage_roots = (
            self.temporary_root.resolve(strict=False),
            self.quarantine_root.resolve(strict=False),
            self.icons_root.resolve(strict=False),
        )
        if len(set(managed_storage_roots)) != len(managed_storage_roots):
            raise ValueError("Temporary, quarantine, and icons roots must be distinct.")
        for managed_root in managed_storage_roots:
            if managed_root == storage_root or not managed_root.is_relative_to(storage_root):
                raise ValueError(
                    "Temporary, quarantine, and icons roots must be descendants of storage_root."
                )
        backup_root = self.backup_root.resolve(strict=False)
        if (
            backup_root == storage_root
            or backup_root.is_relative_to(storage_root)
            or storage_root.is_relative_to(backup_root)
        ):
            raise ValueError(
                "backup_root must remain outside storage_root and the roots must be disjoint."
            )
        configured_database = make_url(self.database_url).database
        if configured_database is not None and configured_database not in {"", ":memory:"}:
            database_path = Path(configured_database).resolve(strict=False)
            if database_path.is_relative_to(backup_root):
                raise ValueError("The SQLite database cannot be stored below backup_root.")

        if self.app_environment is AppEnvironment.PRODUCTION:
            if self.app_debug:
                raise ValueError("Debug mode is forbidden in production.")
            if self.app_secret_key is None or self.csrf_secret is None:
                raise ValueError("Production requires app_secret_key and csrf_secret.")
            if self.session_cookie_secure is False:
                raise ValueError("Secure session cookies cannot be disabled in production.")
            if self.argon2_time_cost < DEFAULT_ARGON2_TIME_COST:
                raise ValueError("Production Argon2 time cost is below the approved minimum.")
            if self.argon2_memory_cost_kib < DEFAULT_ARGON2_MEMORY_COST_KIB:
                raise ValueError("Production Argon2 memory cost is below the approved minimum.")
            if "*" in self.trusted_hosts:
                raise ValueError("Wildcard trusted hosts are forbidden in production.")
            if self.public_base_url.scheme != "https":
                raise ValueError("Production public_base_url must use HTTPS.")
            public_host = urlsplit(str(self.public_base_url)).hostname
            if public_host and public_host not in self.trusted_hosts:
                raise ValueError("The production public host must be included in trusted_hosts.")

            database_name = make_url(self.database_url).database
            if database_name is None or database_name in {"", ":memory:"}:
                raise ValueError("Production requires a persistent SQLite database file.")
            if not Path(database_name).is_absolute():
                raise ValueError("Production SQLite database path must be absolute.")

        return self

    @property
    def effective_session_cookie_secure(self) -> bool:
        """Use secure cookies in production unless explicitly enabled earlier."""

        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.is_production

    @property
    def is_production(self) -> bool:
        """Return whether production-only security rules are active."""

        return self.app_environment is AppEnvironment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return one validated settings instance per process."""

    return AppSettings()
