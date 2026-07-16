"""Bounded no-follow SHA-256 package artifact observation."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from fam_os.registry.package import ArtifactDigest


@dataclass(frozen=True, slots=True)
class Sha256FileArtifactHasher:
    maximum_bytes: int = 128 * 1024**3
    chunk_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if self.maximum_bytes <= 0 or self.chunk_bytes <= 0:
            raise ValueError("artifact hashing bounds must be positive")

    def digest(self, path: Path) -> ArtifactDigest:
        flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("package artifact must be a regular file")
            if metadata.st_size > self.maximum_bytes:
                raise ValueError("package artifact exceeds hashing limit")
            return ArtifactDigest("sha256", _hash_descriptor(descriptor, self))
        finally:
            os.close(descriptor)


def _hash_descriptor(descriptor: int, settings: Sha256FileArtifactHasher) -> str:
    digest = hashlib.sha256()
    total = 0
    while chunk := os.read(descriptor, settings.chunk_bytes):
        total += len(chunk)
        if total > settings.maximum_bytes:
            raise ValueError("package artifact exceeds hashing limit")
        digest.update(chunk)
    return digest.hexdigest()
