"""Exact-range file prefetch and physical-I/O observation."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileReadEvidence:
    bytes_read: int
    physical_read_bytes: int
    digest_sha256: str


class BoundedFilePrefetcher:
    def __init__(self, allowed_root: Path, chunk_bytes: int = 1024**2) -> None:
        self._root = allowed_root.resolve()
        self._chunk_bytes = chunk_bytes

    def read_range(self, path: Path, maximum_bytes: int) -> FileReadEvidence:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._root) or maximum_bytes <= 0:
            raise ValueError("prefetch range escaped its owned root or is unbounded")
        before = _physical_read_bytes()
        digest = hashlib.sha256()
        total = 0
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            while total < maximum_bytes:
                chunk = os.pread(descriptor, min(self._chunk_bytes, maximum_bytes - total), total)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
        finally:
            os.close(descriptor)
        return FileReadEvidence(total, max(0, _physical_read_bytes() - before), digest.hexdigest())


def _physical_read_bytes() -> int:
    values = {}
    for line in Path("/proc/self/io").read_text(encoding="utf-8").splitlines():
        name, value = line.split(":", 1)
        values[name] = int(value.strip())
    return values["read_bytes"]
