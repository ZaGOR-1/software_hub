"""Central safe HTTP error rendering for JSON clients and HTML browsers."""

import logging
from http import HTTPStatus
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.templating import Jinja2Templates
from starlette.types import ExceptionHandler

from app.core.constants import ERROR_TEMPLATE_STATUS_CODES
from app.core.exceptions import ApplicationError, ErrorCode
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)
_TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

_STATUS_MESSAGES: dict[int, tuple[str, str, ErrorCode]] = {
    400: ("Bad request", "The request could not be processed.", ErrorCode.BAD_REQUEST),
    401: (
        "Authentication required",
        "Authentication is required to access this resource.",
        ErrorCode.AUTHENTICATION_REQUIRED,
    ),
    403: ("Access denied", "You do not have access to this resource.", ErrorCode.PERMISSION_DENIED),
    404: ("Not found", "The requested resource was not found.", ErrorCode.NOT_FOUND),
    409: ("Conflict", "The request conflicts with the current state.", ErrorCode.CONFLICT),
    413: (
        "Payload too large",
        "The submitted request is larger than the allowed limit.",
        ErrorCode.PAYLOAD_TOO_LARGE,
    ),
    422: (
        "Invalid data",
        "The submitted data is invalid.",
        ErrorCode.VALIDATION_ERROR,
    ),
    429: (
        "Too many requests",
        "Too many requests were received. Please try again later.",
        ErrorCode.RATE_LIMITED,
    ),
    500: (
        "Internal server error",
        "An unexpected error occurred. Please try again later.",
        ErrorCode.INTERNAL_ERROR,
    ),
    503: (
        "Service unavailable",
        "The service is temporarily unavailable.",
        ErrorCode.SERVICE_UNAVAILABLE,
    ),
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id()


def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


def _status_defaults(status_code: int) -> tuple[str, str, ErrorCode]:
    try:
        fallback_title = HTTPStatus(status_code).phrase
    except ValueError:
        fallback_title = "Error"
    return _STATUS_MESSAGES.get(
        status_code,
        (
            fallback_title,
            "The request could not be processed.",
            ErrorCode.BAD_REQUEST,
        ),
    )


def render_error_response(
    request: Request,
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    title: str | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """Render a content-negotiated error response without internal details."""

    default_title, _, _ = _status_defaults(status_code)
    request_id = _request_id(request)
    response_headers = dict(headers or {})
    response_headers.setdefault("Cache-Control", "no-store")

    if _prefers_html(request):
        template_status = status_code if status_code in ERROR_TEMPLATE_STATUS_CODES else 400
        return _TEMPLATES.TemplateResponse(
            request=request,
            name=f"errors/{template_status}.html",
            context={
                "app_name": request.app.state.settings.app_name,
                "status_code": status_code,
                "title": title or default_title,
                "message": message,
                "request_id": request_id,
            },
            status_code=status_code,
            headers=response_headers,
        )

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code.value,
                "message": message,
                "request_id": request_id,
            }
        },
        headers=response_headers,
    )


async def application_error_handler(request: Request, exc: ApplicationError) -> Response:
    """Map a typed application exception to its declared safe response."""

    title, _, _ = _status_defaults(exc.status_code)
    log_method = logger.error if exc.status_code >= 500 else logger.warning
    log_method(
        "application_error",
        extra={
            "error_code": exc.code.value,
            "status_code": int(exc.status_code),
            "safe_metadata": exc.safe_metadata,
        },
    )
    return render_error_response(
        request,
        status_code=int(exc.status_code),
        code=exc.code,
        message=exc.public_message,
        title=title,
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Render framework HTTP errors through the same public envelope."""

    title, default_message, code = _status_defaults(exc.status_code)
    message = (
        exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else default_message
    )
    return render_error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        title=title,
        headers=dict(exc.headers or {}),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
    """Return a safe validation error without echoing submitted values."""

    logger.warning(
        "request_validation_error",
        extra={"status_code": 422, "validation_error_count": len(exc.errors())},
    )
    title, message, code = _status_defaults(422)
    return render_error_response(
        request,
        status_code=422,
        code=code,
        message=message,
        title=title,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Convert an unexpected exception into a generic production-safe 500."""

    logger.exception(
        "unhandled_exception",
        exc_info=True,
        extra={"status_code": 500, "exception_type": type(exc).__name__},
    )
    title, message, code = _status_defaults(500)
    return render_error_response(
        request,
        status_code=500,
        code=code,
        message=message,
        title=title,
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Register handlers supported directly by Starlette's exception layer."""

    application.add_exception_handler(
        ApplicationError,
        cast(ExceptionHandler, application_error_handler),
    )
    application.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, http_exception_handler),
    )
    application.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )
