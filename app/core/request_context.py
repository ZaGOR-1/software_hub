"""Request-scoped context values used by logging and error responses."""

from contextvars import ContextVar, Token

_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind a request ID to the current asynchronous context."""

    return _request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the request ID context to its previous state."""

    _request_id_context.reset(token)


def get_request_id(default: str = "-") -> str:
    """Return the current request ID or a safe fallback outside requests."""

    return _request_id_context.get() or default
