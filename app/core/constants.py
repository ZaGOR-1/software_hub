"""Application-wide constants that do not depend on runtime configuration."""

from typing import Final

MEBIBYTE: Final[int] = 1024 * 1024
GIBIBYTE: Final[int] = 1024 * MEBIBYTE

MINIMUM_SECRET_LENGTH: Final[int] = 32
DEFAULT_MAX_UPLOAD_SIZE: Final[int] = 2 * GIBIBYTE
MINIMUM_UPLOAD_SIZE: Final[int] = MEBIBYTE
MAXIMUM_UPLOAD_SIZE: Final[int] = 10 * GIBIBYTE

DEFAULT_STORAGE_MIN_FREE_BYTES: Final[int] = GIBIBYTE
MAXIMUM_STORAGE_MIN_FREE_BYTES: Final[int] = 100 * GIBIBYTE
DEFAULT_TEMPORARY_FILE_MAX_AGE_SECONDS: Final[int] = 24 * 60 * 60
MINIMUM_TEMPORARY_FILE_MAX_AGE_SECONDS: Final[int] = 5 * 60
MAXIMUM_TEMPORARY_FILE_MAX_AGE_SECONDS: Final[int] = 30 * 24 * 60 * 60
STORAGE_DIRECTORY_MODE: Final[int] = 0o750
STORAGE_FILE_MODE: Final[int] = 0o640
MAXIMUM_FILENAME_LENGTH: Final[int] = 255
MAXIMUM_FILENAME_BYTES: Final[int] = 255
UPLOAD_TEMPORARY_SUFFIX: Final[str] = ".upload"
DEFAULT_UPLOAD_CHUNK_SIZE: Final[int] = MEBIBYTE
MINIMUM_UPLOAD_CHUNK_SIZE: Final[int] = 64 * 1024
MAXIMUM_UPLOAD_CHUNK_SIZE: Final[int] = 8 * MEBIBYTE
DEFAULT_UPLOAD_MAGIC_SAMPLE_SIZE: Final[int] = MEBIBYTE
MAXIMUM_UPLOAD_MAGIC_SAMPLE_SIZE: Final[int] = 4 * MEBIBYTE
UPLOAD_REQUEST_OVERHEAD_BYTES: Final[int] = 2 * MEBIBYTE
MAXIMUM_FORM_FILES: Final[int] = 1
MAXIMUM_FORM_FIELDS: Final[int] = 64
MAXIMUM_FORM_FIELD_SIZE: Final[int] = 64 * 1024
DEFAULT_CLAMAV_TIMEOUT_SECONDS: Final[int] = 120
MAXIMUM_SCANNER_DETAILS_LENGTH: Final[int] = 500

DEFAULT_SQLITE_BUSY_TIMEOUT_MS: Final[int] = 5_000
MINIMUM_SQLITE_BUSY_TIMEOUT_MS: Final[int] = 100
MAXIMUM_SQLITE_BUSY_TIMEOUT_MS: Final[int] = 60_000

DEFAULT_ALLOWED_EXTENSIONS: Final[tuple[str, ...]] = (".exe", ".msi", ".zip", ".7z")
DEFAULT_TRUSTED_HOSTS: Final[tuple[str, ...]] = ("localhost", "127.0.0.1", "testserver")
DEFAULT_TRUSTED_PROXY_NETWORKS: Final[tuple[str, ...]] = ("127.0.0.1/32", "::1/128")

DEFAULT_SESSION_IDLE_TIMEOUT_SECONDS: Final[int] = 30 * 60
DEFAULT_SESSION_ABSOLUTE_TIMEOUT_SECONDS: Final[int] = 12 * 60 * 60
DEFAULT_SESSION_TOUCH_INTERVAL_SECONDS: Final[int] = 60
DEFAULT_LOGIN_MAX_FAILED_ATTEMPTS: Final[int] = 5
DEFAULT_LOGIN_LOCKOUT_SECONDS: Final[int] = 15 * 60
DEFAULT_CSRF_TOKEN_TTL_SECONDS: Final[int] = 2 * 60 * 60
DEFAULT_LOGIN_CSRF_TTL_SECONDS: Final[int] = 10 * 60
CSRF_TOKEN_MAX_LENGTH: Final[int] = 512
DEFAULT_PASSWORD_MIN_LENGTH: Final[int] = 12
DEFAULT_PASSWORD_MAX_LENGTH: Final[int] = 1024
DEFAULT_ARGON2_TIME_COST: Final[int] = 3
DEFAULT_ARGON2_MEMORY_COST_KIB: Final[int] = 65_536
DEFAULT_ARGON2_PARALLELISM: Final[int] = 4
SESSION_COOKIE_NAME_PATTERN: Final[str] = r"^[A-Za-z0-9_-]{1,64}$"

REQUEST_ID_HEADER: Final[str] = "X-Request-ID"
REQUEST_ID_MAX_LENGTH: Final[int] = 128
REQUEST_ID_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"

FORWARDED_HEADERS: Final[frozenset[bytes]] = frozenset(
    {
        b"forwarded",
        b"x-forwarded-for",
        b"x-forwarded-host",
        b"x-forwarded-port",
        b"x-forwarded-proto",
        b"x-real-ip",
    }
)

SECURITY_HEADERS: Final[dict[str, str]] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-Frame-Options": "DENY",
}

DEFAULT_CONTENT_SECURITY_POLICY: Final[str] = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'"
)

SENSITIVE_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "authorization",
    "cookie",
    "csrf",
    "password",
    "secret",
    "session",
    "token",
)
REDACTED_VALUE: Final[str] = "[REDACTED]"

ERROR_TEMPLATE_STATUS_CODES: Final[frozenset[int]] = frozenset(
    {400, 401, 403, 404, 409, 413, 422, 429, 500, 503}
)

DEFAULT_BACKUP_RETENTION_COUNT: Final[int] = 14
DEFAULT_BACKUP_MIN_FREE_BYTES: Final[int] = GIBIBYTE
MAXIMUM_BACKUP_RETENTION_COUNT: Final[int] = 365
