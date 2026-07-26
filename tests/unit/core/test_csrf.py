"""Unit tests for signed pre-authentication and session-bound CSRF tokens."""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import AppSettings
from app.core.csrf import CSRFTokenService
from app.core.exceptions import CSRFError


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def service(test_settings: AppSettings, clock: MutableClock) -> CSRFTokenService:
    return CSRFTokenService(test_settings, clock=clock)


def test_login_context_round_trip(test_settings: AppSettings) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    csrf = service(test_settings, clock)
    context = csrf.issue_login_context()

    assert context.max_age == test_settings.login_csrf_ttl_seconds
    assert context.cookie_value not in context.token.split(".")[-1]
    csrf.verify_login_token(cookie_value=context.cookie_value, token=context.token)


def test_login_token_requires_cookie_and_form_value(test_settings: AppSettings) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    csrf = service(test_settings, clock)
    context = csrf.issue_login_context()

    with pytest.raises(CSRFError) as missing_cookie:
        csrf.verify_login_token(cookie_value=None, token=context.token)
    assert missing_cookie.value.safe_metadata == {"reason": "login_cookie_missing"}

    with pytest.raises(CSRFError) as missing_token:
        csrf.verify_login_token(cookie_value=context.cookie_value, token=None)
    assert missing_token.value.safe_metadata == {"reason": "missing"}


def test_login_token_rejects_context_mismatch_and_tampering(test_settings: AppSettings) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    csrf = service(test_settings, clock)
    first = csrf.issue_login_context()
    second = csrf.issue_login_context()

    with pytest.raises(CSRFError) as mismatch:
        csrf.verify_login_token(cookie_value=second.cookie_value, token=first.token)
    assert mismatch.value.safe_metadata == {"reason": "context_mismatch"}

    version, issued_at, nonce, signature = first.token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{version}.{issued_at}.{nonce}.{replacement}{signature[1:]}"
    with pytest.raises(CSRFError) as invalid_signature:
        csrf.verify_login_token(cookie_value=first.cookie_value, token=tampered)
    assert invalid_signature.value.safe_metadata == {"reason": "signature_mismatch"}


def test_tokens_enforce_format_size_and_lifetime(test_settings: AppSettings) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    csrf = service(test_settings, clock)
    context = csrf.issue_login_context()

    with pytest.raises(CSRFError) as malformed:
        csrf.verify_login_token(cookie_value=context.cookie_value, token="not-a-token")
    assert malformed.value.safe_metadata == {"reason": "malformed"}

    with pytest.raises(CSRFError) as oversized:
        csrf.verify_login_token(
            cookie_value=context.cookie_value,
            token="x" * (test_settings.csrf_token_max_length + 1),
        )
    assert oversized.value.safe_metadata == {"reason": "oversized"}

    clock.value += timedelta(seconds=test_settings.login_csrf_ttl_seconds + 1)
    with pytest.raises(CSRFError) as expired:
        csrf.verify_login_token(cookie_value=context.cookie_value, token=context.token)
    assert expired.value.safe_metadata == {"reason": "expired"}


def test_token_issued_too_far_in_future_is_rejected(test_settings: AppSettings) -> None:
    issuer_clock = MutableClock(datetime(2026, 7, 23, 12, 2, tzinfo=UTC))
    verifier_clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    issued = service(test_settings, issuer_clock).issue_login_context()

    with pytest.raises(CSRFError) as future:
        service(test_settings, verifier_clock).verify_login_token(
            cookie_value=issued.cookie_value,
            token=issued.token,
        )
    assert future.value.safe_metadata == {"reason": "issued_in_future"}


def test_session_token_is_bound_to_one_session_secret(test_settings: AppSettings) -> None:
    clock = MutableClock(datetime(2026, 7, 23, 12, 0, tzinfo=UTC))
    csrf = service(test_settings, clock)
    first_secret = "1" * 64
    second_secret = "2" * 64
    token = csrf.issue_session_token(first_secret)

    csrf.verify_session_token(csrf_secret_hash=first_secret, token=token)
    with pytest.raises(CSRFError) as wrong_session:
        csrf.verify_session_token(csrf_secret_hash=second_secret, token=token)
    assert wrong_session.value.safe_metadata == {"reason": "signature_mismatch"}

    clock.value += timedelta(seconds=test_settings.csrf_token_ttl_seconds + 1)
    with pytest.raises(CSRFError) as expired:
        csrf.verify_session_token(csrf_secret_hash=first_secret, token=token)
    assert expired.value.safe_metadata == {"reason": "expired"}


def test_invalid_session_context_is_rejected(test_settings: AppSettings) -> None:
    csrf = CSRFTokenService(test_settings)

    with pytest.raises(CSRFError) as invalid_hex:
        csrf.issue_session_token("not-hex")
    assert invalid_hex.value.safe_metadata == {"reason": "invalid_session_context"}

    with pytest.raises(CSRFError) as wrong_length:
        csrf.issue_session_token("ab")
    assert wrong_length.value.safe_metadata == {"reason": "invalid_session_context"}


def test_missing_global_secret_fails_closed(test_settings: AppSettings) -> None:
    settings = test_settings.model_copy(update={"csrf_secret": None})
    with pytest.raises(RuntimeError, match="requires csrf_secret"):
        CSRFTokenService(settings).issue_login_context()
