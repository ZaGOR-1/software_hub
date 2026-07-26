"""Typed application exceptions mapped centrally to safe HTTP responses."""

from collections.abc import Mapping
from enum import StrEnum
from http import HTTPStatus
from typing import Any


class ErrorCode(StrEnum):
    """Stable public error identifiers suitable for UI and logs."""

    BAD_REQUEST = "bad_request"
    AUTHENTICATION_REQUIRED = "authentication_required"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    FILE_VALIDATION_ERROR = "file_validation_error"
    STORAGE_ERROR = "storage_error"
    DUPLICATE_FILE = "duplicate_file"
    AUTHENTICATION_ERROR = "authentication_error"
    CSRF_ERROR = "csrf_error"


class ApplicationError(Exception):
    """Base exception carrying only safe public response metadata."""

    status_code: int = HTTPStatus.BAD_REQUEST
    code: ErrorCode = ErrorCode.BAD_REQUEST
    default_message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        headers: Mapping[str, str] | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.public_message = message or self.default_message
        self.headers = dict(headers or {})
        self.safe_metadata = dict(safe_metadata or {})
        super().__init__(self.public_message)


class EntityNotFound(ApplicationError):
    status_code = HTTPStatus.NOT_FOUND
    code = ErrorCode.NOT_FOUND
    default_message = "The requested resource was not found."


class PermissionDenied(ApplicationError):
    status_code = HTTPStatus.FORBIDDEN
    code = ErrorCode.PERMISSION_DENIED
    default_message = "You do not have permission to perform this action."


class EntityConflict(ApplicationError):
    status_code = HTTPStatus.CONFLICT
    code = ErrorCode.CONFLICT
    default_message = "A resource with the same unique value already exists."


class PayloadTooLarge(ApplicationError):
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = ErrorCode.PAYLOAD_TOO_LARGE
    default_message = "The uploaded file is too large."


class ValidationError(ApplicationError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = ErrorCode.VALIDATION_ERROR
    default_message = "The submitted data is invalid."


class InvalidStateTransition(ApplicationError):
    status_code = HTTPStatus.CONFLICT
    code = ErrorCode.INVALID_STATE_TRANSITION
    default_message = "The requested state transition is not allowed."


class FileValidationError(ApplicationError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = ErrorCode.FILE_VALIDATION_ERROR
    default_message = "The uploaded file did not pass validation."


class StorageError(ApplicationError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = ErrorCode.STORAGE_ERROR
    default_message = "File storage is temporarily unavailable."


class DuplicateFileError(ApplicationError):
    status_code = HTTPStatus.CONFLICT
    code = ErrorCode.DUPLICATE_FILE
    default_message = "An identical file already exists."


class AuthenticationError(ApplicationError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = ErrorCode.AUTHENTICATION_ERROR
    default_message = "Authentication failed."


class CSRFError(ApplicationError):
    status_code = HTTPStatus.FORBIDDEN
    code = ErrorCode.CSRF_ERROR
    default_message = "The security token is invalid or expired."


class ServiceUnavailable(ApplicationError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = ErrorCode.SERVICE_UNAVAILABLE
    default_message = "The service is temporarily unavailable."


class RateLimitError(ApplicationError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = ErrorCode.RATE_LIMITED
    default_message = "Too many requests. Please try again later."
