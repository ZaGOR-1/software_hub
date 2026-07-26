"""Domain enumerations persisted by the Software Hub data model."""

from enum import StrEnum


class SoftwareStatus(StrEnum):
    """Lifecycle states for catalog software."""

    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    ARCHIVED = "archived"
    DISABLED = "disabled"


class Visibility(StrEnum):
    """Visibility shared by software and release files."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class ReleaseChannel(StrEnum):
    """Supported release channels."""

    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"
    NIGHTLY = "nightly"
    LEGACY = "legacy"


class ReleaseStatus(StrEnum):
    """Lifecycle states for a software release."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DISABLED = "disabled"


class FileStatus(StrEnum):
    """Lifecycle states for uploaded release files."""

    QUARANTINE = "quarantine"
    READY = "ready"
    PUBLISHED = "published"
    DISABLED = "disabled"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class Architecture(StrEnum):
    """Supported CPU architecture labels."""

    X64 = "x64"
    X86 = "x86"
    ARM64 = "arm64"
    UNIVERSAL = "universal"
    OTHER = "other"


class PackageType(StrEnum):
    """Supported package classifications."""

    INSTALLER = "installer"
    PORTABLE = "portable"
    ARCHIVE = "archive"
    MSI = "msi"
    OTHER = "other"


class SignatureStatus(StrEnum):
    """Digital-signature verification state."""

    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID = "invalid"
    UNSIGNED = "unsigned"
    NOT_CHECKED = "not_checked"


class ScannerStatus(StrEnum):
    """Optional malware scanner state."""

    NOT_SCANNED = "not_scanned"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    UNAVAILABLE = "unavailable"
