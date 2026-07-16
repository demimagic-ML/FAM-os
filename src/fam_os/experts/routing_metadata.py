"""Versioned semantic routing embeddings and similarity evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from fam_os.experts.capabilities import require_expert_capabilities
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.package import ArtifactDigest


EXPERT_ROUTING_METADATA_VERSION = "fam.expert.routing-metadata/v1alpha1"


@dataclass(frozen=True, slots=True)
class ExpertRoutingEmbedding:
    embedding_id: str
    coordinate: ExpertPackageCoordinate
    expert_id: str
    publisher_id: str
    embedding_space_id: str
    generator_id: str
    generator_version: str
    vector: tuple[float, ...]
    capabilities: tuple[str, ...]
    source_digest: ArtifactDigest
    generated_at: datetime
    benchmark_run_ids: tuple[str, ...] = ()
    contract_version: str = EXPERT_ROUTING_METADATA_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EXPERT_ROUTING_METADATA_VERSION:
            raise ValueError("unsupported expert routing metadata contract_version")
        for name in (
            "embedding_id", "expert_id", "publisher_id", "embedding_space_id",
            "generator_id", "generator_version",
        ):
            _require_text(getattr(self, name), name)
        _require_vector(self.vector)
        require_expert_capabilities(self.capabilities, publisher_id=self.publisher_id)
        _require_unique_text(self.benchmark_run_ids, "benchmark_run_ids", allow_empty=True)
        if self.source_digest.algorithm != "sha256":
            raise ValueError("routing embedding source digest must use SHA-256")
        _require_aware(self.generated_at)


@dataclass(frozen=True, slots=True)
class RoutingEmbeddingQuery:
    embedding_space_id: str
    vector: tuple[float, ...]
    required_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.embedding_space_id, "embedding_space_id")
        _require_vector(self.vector)
        if self.required_capabilities:
            require_expert_capabilities(self.required_capabilities, publisher_id=None)


@dataclass(frozen=True, slots=True)
class ExpertRoutingMatch:
    coordinate: ExpertPackageCoordinate
    expert_id: str
    embedding_id: str
    cosine_similarity: float
    benchmark_run_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not -1.0 <= self.cosine_similarity <= 1.0:
            raise ValueError("cosine similarity must be between -1 and 1")


def _require_vector(vector: tuple[float, ...]) -> None:
    if not 1 <= len(vector) <= 4096:
        raise ValueError("routing vector dimensions must be between 1 and 4096")
    if any(not math.isfinite(value) for value in vector):
        raise ValueError("routing vector values must be finite")
    magnitude = math.sqrt(sum(value * value for value in vector))
    if not math.isclose(magnitude, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("routing vectors must be L2 normalized")


def _require_unique_text(values: tuple[str, ...], name: str, *, allow_empty: bool) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{name} must not be empty")
    if len(set(values)) != len(values) or any(not value.strip() for value in values):
        raise ValueError(f"{name} values must be non-empty and unique")


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
