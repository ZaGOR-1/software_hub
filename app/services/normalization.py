"""Normalization and validation helpers shared by application services."""

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NON_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")

_TRANSLITERATION = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "h",
        "ґ": "g",
        "д": "d",
        "е": "e",
        "є": "ie",
        "ж": "zh",
        "з": "z",
        "и": "y",
        "і": "i",
        "ї": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ь": "",
        "ю": "iu",
        "я": "ia",
        "ъ": "",
        "ы": "y",
        "э": "e",
        "ё": "yo",
    }
)


def normalize_name(value: str, *, max_length: int) -> str:
    """Collapse whitespace and enforce a non-empty bounded display name."""

    normalized = " ".join(value.split())
    if not normalized:
        msg = "Name cannot be empty."
        raise ValueError(msg)
    if len(normalized) > max_length:
        msg = f"Name must not exceed {max_length} characters."
        raise ValueError(msg)
    return normalized


def generate_slug(value: str, *, max_length: int) -> str:
    """Generate a deterministic ASCII slug, including Ukrainian transliteration."""

    lowered = value.strip().casefold().translate(_TRANSLITERATION)
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_value = decomposed.encode("ascii", "ignore").decode("ascii")
    generated = _NON_SLUG_PATTERN.sub("-", ascii_value).strip("-")
    generated = re.sub(r"-+", "-", generated)[:max_length].strip("-")
    if not generated:
        msg = "Slug could not be generated; enter an explicit ASCII slug."
        raise ValueError(msg)
    return generated


def normalize_slug(value: str, *, max_length: int, fallback: str | None = None) -> str:
    """Normalize an explicit ASCII slug or generate one from a display name."""

    candidate = value.strip()
    if not candidate and fallback is not None:
        candidate = generate_slug(fallback, max_length=max_length)
    normalized = candidate.casefold().replace("_", "-")
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized or not _SLUG_PATTERN.fullmatch(normalized):
        msg = "Slug must contain lowercase ASCII letters, digits, and single hyphens."
        raise ValueError(msg)
    if len(normalized) > max_length:
        msg = f"Slug must not exceed {max_length} characters."
        raise ValueError(msg)
    return normalized


def normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
    """Trim optional plain text while retaining internal line breaks."""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        msg = f"Text must not exceed {max_length} characters."
        raise ValueError(msg)
    return normalized


def normalize_http_url(value: str | None, *, max_length: int = 2_048) -> str | None:
    """Validate an optional absolute HTTP(S) URL without fetching it."""

    normalized = normalize_optional_text(value, max_length=max_length)
    if normalized is None:
        return None
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        msg = "URL must be an absolute HTTP or HTTPS address."
        raise ValueError(msg)
    if parsed.username is not None or parsed.password is not None:
        msg = "URL credentials are not allowed."
        raise ValueError(msg)
    if any(character in normalized for character in ("\r", "\n", "\x00")):
        msg = "URL contains forbidden characters."
        raise ValueError(msg)
    return urlunsplit(parsed)
