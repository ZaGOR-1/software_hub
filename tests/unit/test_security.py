"""Unit tests for password and session cryptography primitives."""

from typing import Any

import pytest
from app.core.config import AppSettings
from app.core.exceptions import ValidationError
from app.core.security import (
    PasswordService,
    derive_csrf_secret_hash,
    generate_session_token,
    hash_session_token,
    hmac_identifier,
    normalize_username,
)


def make_settings(**updates: object) -> AppSettings:
    values: dict[str, Any] = {
        "app_environment": "test",
        "app_secret_key": "test-app-secret-0123456789-ABCDEFGH",
        "csrf_secret": "test-csrf-secret-9876543210-HGFEDCBA",
        "argon2_time_cost": 1,
        "argon2_memory_cost_kib": 1_024,
        "argon2_parallelism": 1,
    }
    values.update(updates)
    return AppSettings(**values)


def test_username_normalization_and_validation() -> None:
    assert normalize_username("  Admin.User  ") == "admin.user"

    for value in ("ab", "admin space", "_admin", "admin_", "адмін"):
        with pytest.raises(ValidationError):
            normalize_username(value)


def test_password_hashing_uses_argon2id_and_verifies() -> None:
    service = PasswordService(make_settings())
    password_hash = service.hash_password("correct horse battery staple", username="admin")

    assert password_hash.startswith("$argon2id$")
    assert service.verify_password("correct horse battery staple", password_hash) is True
    assert service.verify_password("wrong password", password_hash) is False
    assert service.verify_password("anything", "not-an-argon2-hash") is False
    assert service.needs_rehash("not-an-argon2-hash") is True


def test_password_policy_rejects_weak_shape() -> None:
    service = PasswordService(make_settings(password_min_length=12, password_max_length=64))

    with pytest.raises(ValidationError, match="at least"):
        service.hash_password("too-short")
    with pytest.raises(ValidationError, match="at most"):
        service.hash_password("x" * 65)
    with pytest.raises(ValidationError, match="whitespace"):
        service.hash_password(" leading-or-trailing ")
    with pytest.raises(ValidationError, match="username"):
        service.hash_password("administrator", username="administrator")


def test_password_rehash_detection_and_unknown_user_work() -> None:
    old = PasswordService(make_settings(argon2_time_cost=1))
    new = PasswordService(make_settings(argon2_time_cost=2))
    password_hash = old.hash_password("a sufficiently long password")

    assert old.needs_rehash(password_hash) is False
    assert new.needs_rehash(password_hash) is True
    new.verify_unknown_user("arbitrary password")


def test_session_token_and_hmac_helpers() -> None:
    first = generate_session_token()
    second = generate_session_token()

    assert first != second
    assert len(first) >= 43
    assert len(hash_session_token(first)) == 64
    assert hash_session_token(first) == hash_session_token(first)
    assert hmac_identifier("secret", "ip", "127.0.0.1") == hmac_identifier(
        "secret", "ip", "127.0.0.1"
    )
    assert hmac_identifier("secret", "ip", "127.0.0.1") != hmac_identifier(
        "secret", "ua", "127.0.0.1"
    )
    assert hmac_identifier("secret", "ip", None) is None
    assert hmac_identifier("secret", "ip", "   ") is None
    assert len(derive_csrf_secret_hash("csrf-secret", "a" * 64)) == 64
