"""Bounded SHA-256 helper tests."""

from io import BytesIO
from pathlib import Path

import pytest
from app.storage.hashing import StreamingSHA256, sha256_file, sha256_stream


def test_streaming_hash_ignores_empty_chunks_and_counts_bytes(tmp_path: Path) -> None:
    digest = StreamingSHA256()
    digest.update(b"")
    digest.update(b"abc")
    assert digest.bytes_processed == 3
    assert digest.hexdigest() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    value, size = sha256_stream(BytesIO(b"abc"), chunk_size=2)
    assert value == digest.hexdigest()
    assert size == 3

    path = tmp_path / "file.bin"
    path.write_bytes(b"abc")
    assert sha256_file(path, chunk_size=1) == (digest.hexdigest(), 3)


def test_hash_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        sha256_stream(BytesIO(b"abc"), chunk_size=0)
