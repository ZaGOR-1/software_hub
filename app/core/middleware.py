"""ASGI middleware for correlation, proxy trust, logging and security headers."""

import logging
import re
from collections.abc import Iterable
from ipaddress import ip_address, ip_network
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import AppSettings
from app.core.constants import FORWARDED_HEADERS, REQUEST_ID_PATTERN, SECURITY_HEADERS
from app.core.error_handlers import unhandled_exception_handler
from app.core.request_context import bind_request_id, reset_request_id

logger = logging.getLogger("software_hub.request")


class RequestIdMiddleware:
    """Validate or generate a request ID and return it on every HTTP response."""

    def __init__(self, app: ASGIApp, *, header_name: str, max_length: int) -> None:
        self.app = app
        self.header_name = header_name
        self.max_length = max_length
        self.pattern = re.compile(REQUEST_ID_PATTERN)

    def _resolve_request_id(self, scope: Scope) -> str:
        candidate = Headers(scope=scope).get(self.header_name)
        if (
            candidate
            and len(candidate) <= self.max_length
            and self.pattern.fullmatch(candidate) is not None
        ):
            return candidate
        return uuid4().hex

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        token = bind_request_id(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[self.header_name] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            reset_request_id(token)


class RequestLoggingMiddleware:
    """Emit one bounded structured completion event per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            route = scope.get("route")
            route_path = getattr(route, "path", scope.get("path", "-"))
            client = scope.get("client")
            client_ip = client[0] if client else "-"
            logger.info(
                "request_completed",
                extra={
                    "method": scope.get("method", "-"),
                    "route": route_path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )


class SecurityHeadersMiddleware:
    """Add baseline browser security headers without replacing Nginx hardening."""

    def __init__(self, app: ASGIApp, *, content_security_policy: str) -> None:
        self.app = app
        self.content_security_policy = content_security_policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        async def add_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    if name not in headers:
                        headers[name] = value
                if (
                    not path.startswith(("/docs", "/redoc", "/openapi.json"))
                    and "Content-Security-Policy" not in headers
                ):
                    headers["Content-Security-Policy"] = self.content_security_policy
            await send(message)

        await self.app(scope, receive, add_headers)


class TrustedProxyMiddleware:
    """Strip spoofable forwarding headers from requests not sent by a trusted proxy."""

    def __init__(self, app: ASGIApp, *, trusted_networks: Iterable[str]) -> None:
        self.app = app
        self.trusted_networks = tuple(
            ip_network(network, strict=False) for network in trusted_networks
        )

    def _is_trusted(self, scope: Scope) -> bool:
        client = scope.get("client")
        if not client:
            return False
        try:
            peer = ip_address(client[0])
        except ValueError:
            return False
        return any(peer in network for network in self.trusted_networks)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trusted = self._is_trusted(scope)
        updated_scope = scope
        if not trusted:
            updated_scope = dict(scope)
            updated_scope["headers"] = [
                (name, value)
                for name, value in scope.get("headers", [])
                if name.lower() not in FORWARDED_HEADERS
            ]

        state = updated_scope.setdefault("state", {})
        state["trusted_proxy"] = trusted
        await self.app(updated_scope, receive, send)


class UnhandledExceptionMiddleware:
    """Render unexpected errors inside the user middleware stack."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception as exc:  # noqa: BLE001 - this is the outer application boundary.
            request = Request(scope, receive=receive)
            response = await unhandled_exception_handler(request, exc)
            await response(scope, receive, send)


def install_middleware(application: FastAPI, settings: AppSettings) -> None:
    """Install middleware from innermost to outermost in intentional order."""

    application.add_middleware(UnhandledExceptionMiddleware)

    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.trusted_hosts),
        www_redirect=False,
    )
    application.add_middleware(
        TrustedProxyMiddleware,
        trusted_networks=settings.trusted_proxy_networks,
    )
    if settings.security_headers_enabled:
        application.add_middleware(
            SecurityHeadersMiddleware,
            content_security_policy=settings.content_security_policy,
        )
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        RequestIdMiddleware,
        header_name=settings.request_id_header,
        max_length=settings.request_id_max_length,
    )
