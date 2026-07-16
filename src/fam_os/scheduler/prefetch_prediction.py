"""Historical access sequences and bounded next-artifact prediction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.scheduler.cache_contracts import CacheTier


PREFETCH_CONTRACT_VERSION = "fam.scheduler.predictive-prefetch/v1alpha1"
PREFETCH_PREDICTOR_VERSION = "fam.scheduler.transition-predictor/v1"


@dataclass(frozen=True, slots=True)
class ArtifactAccessSequence:
    sequence_id: str
    observed_at: datetime
    artifact_ids: tuple[str, ...]
    source_evidence_digest_sha256: str

    def __post_init__(self) -> None:
        _text(self.sequence_id, "sequence_id")
        _time(self.observed_at, "observed_at")
        if len(self.artifact_ids) < 2 or any(not value.strip() for value in self.artifact_ids):
            raise ValueError("prefetch history requires at least two artifact accesses")
        _digest(self.source_evidence_digest_sha256)


@dataclass(frozen=True, slots=True)
class PrefetchCandidate:
    artifact_id: str
    tier: CacheTier
    artifact_bytes: int
    requested_prefetch_bytes: int
    expected_reload_cost_ms: float

    def __post_init__(self) -> None:
        _text(self.artifact_id, "artifact_id")
        if self.artifact_bytes <= 0 or not 0 < self.requested_prefetch_bytes <= self.artifact_bytes:
            raise ValueError("prefetch candidate byte bounds are invalid")
        if self.expected_reload_cost_ms <= 0:
            raise ValueError("prefetch candidate requires positive reload cost")


@dataclass(frozen=True, slots=True)
class PrefetchPredictionRequest:
    request_id: str
    current_artifact_id: str
    requested_at: datetime
    candidates: tuple[PrefetchCandidate, ...]
    history: tuple[ArtifactAccessSequence, ...]
    minimum_transition_observations: int
    minimum_confidence: float
    horizon_seconds: int
    predictor_version: str = PREFETCH_PREDICTOR_VERSION
    contract_version: str = PREFETCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PREFETCH_CONTRACT_VERSION or self.predictor_version != PREFETCH_PREDICTOR_VERSION:
            raise ValueError("unsupported prefetch prediction version")
        _text(self.request_id, "request_id")
        _text(self.current_artifact_id, "current_artifact_id")
        _time(self.requested_at, "requested_at")
        ids = tuple(item.artifact_id for item in self.candidates)
        if not ids or len(ids) != len(set(ids)) or not self.history:
            raise ValueError("prefetch prediction candidates/history must be non-empty and unique")
        if self.minimum_transition_observations < 2:
            raise ValueError("prefetch requires at least two transition observations")
        if not 0.5 <= self.minimum_confidence <= 1 or self.horizon_seconds <= 0:
            raise ValueError("prefetch confidence or horizon is invalid")


@dataclass(frozen=True, slots=True)
class PrefetchPrediction:
    prediction_id: str
    request_id: str
    candidate: PrefetchCandidate
    transition_observations: int
    outgoing_observations: int
    confidence: float
    predicted_at: datetime
    expires_at: datetime
    source_sequence_ids: tuple[str, ...]
    predictor_version: str = PREFETCH_PREDICTOR_VERSION
    contract_version: str = PREFETCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PREFETCH_CONTRACT_VERSION or self.predictor_version != PREFETCH_PREDICTOR_VERSION:
            raise ValueError("unsupported prefetch prediction version")
        _text(self.prediction_id, "prediction_id")
        _text(self.request_id, "request_id")
        _time(self.predicted_at, "predicted_at")
        _time(self.expires_at, "expires_at")
        if self.expires_at <= self.predicted_at:
            raise ValueError("prefetch prediction expiry must follow prediction")
        if not 2 <= self.transition_observations <= self.outgoing_observations:
            raise ValueError("prefetch transition counts are invalid")
        if abs(self.confidence - self.transition_observations / self.outgoing_observations) > 1e-12:
            raise ValueError("prefetch confidence is inconsistent")
        if len(self.source_sequence_ids) != self.transition_observations:
            raise ValueError("prefetch prediction must retain every supporting sequence")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("prefetch source digest must be lowercase SHA-256")
