"""Streaming SHA-256 helpers for uploaded files and maintenance checks."""

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Protocol


class _HashProtocol(Protocol):
    def update(self, data: bytes) -> None: ...

    def hexdigest(self) -> str: ...


@dataclass(slots=True)
class StreamingSHA256:
    """Incrementally calculate one lowercase SHA-256 digest."""

    _hasher: _HashProtocol = field(default_factory=sha256, init=False, repr=False)
    bytes_processed: int = 0

    def update(self, chunk: bytes) -> None:
        """Consume one non-empty byte chunk."""

        if not chunk:
            return
        self._hasher.update(chunk)
        self.bytes_processed += len(chunk)

    def hexdigest(self) -> str:
        """Return the current lowercase hexadecimal digest."""

        return self._hasher.hexdigest()


def sha256_stream(stream: BinaryIO, *, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    """Hash a binary stream without loading it into memory."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    digest = StreamingSHA256()
    while chunk := stream.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest(), digest.bytes_processed


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    """Hash one regular file with bounded memory use."""

    with path.open("rb") as stream:
        return sha256_stream(stream, chunk_size=chunk_size)
