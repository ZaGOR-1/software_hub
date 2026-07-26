"""Session-bound and pre-authentication CSRF token primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.core.config import AppSettings
from app.core.exceptions import CSRFError
from app.core.time import utc_now

Clock = Callable[[], datetime]

_TOKEN_VERSION = "v1"  # nosec B105  # noqa: S105
_TOKEN_NONCE_BYTES = 32
_TOKEN_MAC_BYTES = hashlib.sha256().digest_size
_TOKEN_PATTERN = re.compile(
    r"^v1\.(?P<issued_at>[0-9]{1,12})\.(?P<nonce>[A-Za-z0-9_-]{32,128})\."
    r"(?P<mac>[A-Za-z0-9_-]{43})$"
)
_MAX_FUTURE_SKEW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class LoginCSRFContext:
    """Short-lived pre-authentication cookie and its signed form token."""

    cookie_value: str
    token: str
    max_age: int


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes | None:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except ValueError, TypeError:
        return None


def _mac(key: bytes, *, purpose: str, issued_at: int, nonce: str) -> bytes:
    payload = f"{_TOKEN_VERSION}\x00{purpose}\x00{issued_at}\x00{nonce}".encode("ascii")
    return hmac.new(key, payload, hashlib.sha256).digest()


class CSRFTokenService:
    """Issue and verify signed tokens without storing raw CSRF values in the database."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self.settings = settings
        self.clock = clock

    def _global_key(self) -> bytes:
        secret = self.settings.csrf_secret
        if secret is None:
            raise RuntimeError("CSRF protection requires csrf_secret.")
        return secret.get_secret_value().encode("utf-8")

    def _issue(self, *, key: bytes, purpose: str, nonce: str | None = None) -> str:
        issued_at = int(self.clock().timestamp())
        resolved_nonce = nonce or secrets.token_urlsafe(_TOKEN_NONCE_BYTES)
        signature = _encode(
            _mac(
                key,
                purpose=purpose,
                issued_at=issued_at,
                nonce=resolved_nonce,
            )
        )
        return f"{_TOKEN_VERSION}.{issued_at}.{resolved_nonce}.{signature}"

    def _verify(
        self,
        token: str | None,
        *,
        key: bytes,
        purpose: str,
        ttl_seconds: int,
        expected_nonce: str | None = None,
    ) -> None:
        if token is None or not token:
            raise CSRFError(safe_metadata={"reason": "missing"})
        if len(token) > self.settings.csrf_token_max_length:
            raise CSRFError(safe_metadata={"reason": "oversized"})

        match = _TOKEN_PATTERN.fullmatch(token)
        if match is None:
            raise CSRFError(safe_metadata={"reason": "malformed"})

        issued_at = int(match.group("issued_at"))
        nonce = match.group("nonce")
        supplied_mac = _decode(match.group("mac"))
        if supplied_mac is None or len(supplied_mac) != _TOKEN_MAC_BYTES:
            raise CSRFError(safe_metadata={"reason": "malformed"})

        now_timestamp = int(self.clock().timestamp())
        age = now_timestamp - issued_at
        if age < -_MAX_FUTURE_SKEW_SECONDS:
            raise CSRFError(safe_metadata={"reason": "issued_in_future"})
        if age > ttl_seconds:
            raise CSRFError(safe_metadata={"reason": "expired"})

        if expected_nonce is not None and not hmac.compare_digest(nonce, expected_nonce):
            raise CSRFError(safe_metadata={"reason": "context_mismatch"})

        expected_mac = _mac(
            key,
            purpose=purpose,
            issued_at=issued_at,
            nonce=nonce,
        )
        if not hmac.compare_digest(supplied_mac, expected_mac):
            raise CSRFError(safe_metadata={"reason": "signature_mismatch"})

    def issue_login_context(self) -> LoginCSRFContext:
        """Create a short-lived signed token bound to an HttpOnly nonce cookie."""

        nonce = secrets.token_urlsafe(_TOKEN_NONCE_BYTES)
        return LoginCSRFContext(
            cookie_value=nonce,
            token=self._issue(key=self._global_key(), purpose="login", nonce=nonce),
            max_age=self.settings.login_csrf_ttl_seconds,
        )

    def verify_login_token(self, *, cookie_value: str | None, token: str | None) -> None:
        """Verify the pre-authentication login token and matching nonce cookie."""

        if cookie_value is None or not cookie_value:
            raise CSRFError(safe_metadata={"reason": "login_cookie_missing"})
        self._verify(
            token,
            key=self._global_key(),
            purpose="login",
            ttl_seconds=self.settings.login_csrf_ttl_seconds,
            expected_nonce=cookie_value,
        )

    def issue_session_token(self, csrf_secret_hash: str) -> str:
        """Create a form token bound to one authenticated server-side session."""

        return self._issue(
            key=self._session_key(csrf_secret_hash),
            purpose="session",
        )

    def verify_session_token(self, *, csrf_secret_hash: str, token: str | None) -> None:
        """Verify a token against the per-session derived CSRF key."""

        self._verify(
            token,
            key=self._session_key(csrf_secret_hash),
            purpose="session",
            ttl_seconds=self.settings.csrf_token_ttl_seconds,
        )

    @staticmethod
    def _session_key(csrf_secret_hash: str) -> bytes:
        try:
            key = bytes.fromhex(csrf_secret_hash)
        except ValueError as exc:
            raise CSRFError(safe_metadata={"reason": "invalid_session_context"}) from exc
        if len(key) != _TOKEN_MAC_BYTES:
            raise CSRFError(safe_metadata={"reason": "invalid_session_context"})
        return key
