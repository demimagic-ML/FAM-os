"""Observed provider artifact identity used by non-copying package stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fam_os.registry.package import ArtifactDigest


@dataclass(frozen=True, slots=True)
class RuntimeArtifactObservation:
    artifact_ref: str
    digest: ArtifactDigest
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.artifact_ref.strip():
            raise ValueError("runtime artifact_ref must not be empty")
        if self.digest.algorithm != "sha256":
            raise ValueError("runtime artifact observation requires SHA-256")
        if self.size_bytes <= 0:
            raise ValueError("runtime artifact size must be positive")


class RuntimeArtifactCatalog(Protocol):
    def observe(self, artifact_ref: str) -> RuntimeArtifactObservation: ...
