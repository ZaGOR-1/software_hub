"""Authentication and session cryptography primitives."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

from app.core.config import AppSettings
from app.core.exceptions import ValidationError

_USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,98}[a-z0-9])?$")
_SESSION_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class Argon2Parameters:
    """Explicit Argon2id parameters used by the password service."""

    time_cost: int
    memory_cost_kib: int
    parallelism: int
    hash_len: int = 32
    salt_len: int = 16


@lru_cache(maxsize=16)
def _build_hasher(parameters: Argon2Parameters) -> PasswordHasher:
    return PasswordHasher(
        time_cost=parameters.time_cost,
        memory_cost=parameters.memory_cost_kib,
        parallelism=parameters.parallelism,
        hash_len=parameters.hash_len,
        salt_len=parameters.salt_len,
        type=Type.ID,
    )


@lru_cache(maxsize=16)
def _dummy_hash(parameters: Argon2Parameters) -> str:
    """Build one process-local hash used to equalize unknown-user login work."""

    return _build_hasher(parameters).hash("software-hub-login-timing-placeholder")


class PasswordService:
    """Validate password policy and perform Argon2id hashing and verification."""

    def __init__(self, settings: AppSettings) -> None:
        self.minimum_length = settings.password_min_length
        self.maximum_length = settings.password_max_length
        self.parameters = Argon2Parameters(
            time_cost=settings.argon2_time_cost,
            memory_cost_kib=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
        )
        self.hasher = _build_hasher(self.parameters)
        self.dummy_hash = _dummy_hash(self.parameters)

    def validate(self, password: str, *, username: str | None = None) -> None:
        """Apply a length-focused password policy without brittle composition rules."""

        if len(password) < self.minimum_length:
            raise ValidationError(
                f"Password must contain at least {self.minimum_length} characters."
            )
        if len(password) > self.maximum_length:
            raise ValidationError(
                f"Password must contain at most {self.maximum_length} characters."
            )
        if password != password.strip():
            raise ValidationError("Password cannot start or end with whitespace.")
        if username is not None and password.casefold() == username.casefold():
            raise ValidationError("Password cannot be identical to the username.")

    def hash_password(self, password: str, *, username: str | None = None) -> str:
        """Validate and hash a password using Argon2id."""

        self.validate(password, username=username)
        return self.hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password and collapse malformed hashes into authentication failure."""

        try:
            return bool(self.hasher.verify(password_hash, password))
        except VerificationError, InvalidHashError:
            return False

    def verify_unknown_user(self, password: str) -> None:
        """Spend comparable Argon2 work when the username does not exist."""

        self.verify_password(password, self.dummy_hash)

    def needs_rehash(self, password_hash: str) -> bool:
        """Return whether a valid hash should be upgraded to current parameters."""

        try:
            return self.hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True


def normalize_username(username: str) -> str:
    """Normalize administrator usernames to a stable lowercase representation."""

    normalized = username.strip().casefold()
    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise ValidationError(
            "Username must contain 3 to 100 lowercase letters, digits, dots, "
            "underscores or hyphens."
        )
    return normalized


def generate_session_token() -> str:
    """Return an unpredictable URL-safe session bearer token."""

    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Hash a raw bearer token before database lookup or persistence."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hmac_identifier(secret: str, purpose: str, value: str | None) -> str | None:
    """Create a non-reversible, purpose-separated identifier for audit metadata."""

    if value is None or not value.strip():
        return None
    payload = f"{purpose}\x00{value.strip()}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def derive_csrf_secret_hash(csrf_secret: str, session_token_hash: str) -> str:
    """Derive a session-bound value reserved for the Phase 7 CSRF protocol."""

    return hmac_identifier(csrf_secret, "csrf-session", session_token_hash) or ""
