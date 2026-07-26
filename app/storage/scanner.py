"""Optional malware-scanner interface with a safe ClamAV command adapter."""

from __future__ import annotations

# This adapter executes a fixed local scanner argv without a shell.
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Protocol, runtime_checkable

from fastapi import Depends, Request

from app.core.config import AppSettings
from app.models.enums import ScannerStatus


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Sanitized result persisted with release-file metadata."""

    status: ScannerStatus
    details: str | None = None


@runtime_checkable
class FileScanner(Protocol):
    """Small scanner contract independent of ClamAV availability."""

    def scan(self, path: Path) -> ScanResult:
        """Inspect one private regular file without modifying it."""

        ...


@dataclass(frozen=True, slots=True)
class UnavailableScanner:
    """Explicit no-scanner implementation for the base MVP."""

    reason: str = "Malware scanning is disabled."

    def scan(self, path: Path) -> ScanResult:
        del path
        return ScanResult(ScannerStatus.UNAVAILABLE, self.reason)


@dataclass(frozen=True, slots=True)
class ClamAVCommandScanner:
    """Run a fixed local clamscan executable without a shell."""

    command: str
    timeout_seconds: int

    def scan(self, path: Path) -> ScanResult:
        try:
            completed = subprocess.run(  # nosec B603  # noqa: S603
                [self.command, "--no-summary", "--infected", "--", str(path)],
                check=False,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError:
            return ScanResult(ScannerStatus.UNAVAILABLE, "ClamAV executable is unavailable.")
        except subprocess.TimeoutExpired:
            return ScanResult(ScannerStatus.ERROR, "Malware scan timed out.")
        except OSError:
            return ScanResult(ScannerStatus.ERROR, "Malware scanner could not be started.")

        if completed.returncode == 0:
            return ScanResult(ScannerStatus.CLEAN, "No malware was reported by ClamAV.")
        if completed.returncode == 1:
            return ScanResult(ScannerStatus.INFECTED, "ClamAV reported an infected file.")
        return ScanResult(ScannerStatus.ERROR, "ClamAV returned an unexpected error.")


def create_file_scanner(settings: AppSettings) -> FileScanner:
    """Create the configured scanner without making it a hard dependency."""

    if not settings.clamav_enabled:
        return UnavailableScanner()
    return ClamAVCommandScanner(
        command=settings.clamav_command,
        timeout_seconds=settings.clamav_timeout_seconds,
    )


def get_file_scanner(request: Request) -> FileScanner:
    """Resolve the process-level scanner implementation."""

    scanner = getattr(request.app.state, "file_scanner", None)
    if not isinstance(scanner, FileScanner):
        raise RuntimeError("File scanner infrastructure is not initialized.")  # noqa: TRY004
    return scanner


ScannerDependency = Annotated[FileScanner, Depends(get_file_scanner)]
