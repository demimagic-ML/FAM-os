"""Content-free live prediction and model-prewarm records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


LIVE_ADAPTATION_CONTRACT_VERSION = "fam.adaptation.live-prediction/v1alpha1"


class ModelPrewarmSource(StrEnum):
    ESCALATION = "escalation"
    TRANSITION = "transition"
    FREQUENCY = "frequency"


class ModelPrewarmStatus(StrEnum):
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LiveAdaptationSnapshot:
    snapshot_id: str
    workflow_id: str
    created_at: datetime
    observation_count: int
    predicted_context_tokens: int
    escalation_probability: float
    prewarm_escalation: bool
    frequency_model_refs: tuple[str, ...]
    transition_model_ref: str | None
    transition_confidence: float | None
    source_learning_ids: tuple[str, ...]
    source_evidence_sha256: str
    local_only: bool = True
    advisory_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _text(self.workflow_id, "workflow_id")
        _time(self.created_at)
        if self.observation_count != len(self.source_learning_ids):
            raise ValueError("live snapshot must retain every source learning identity")
        if self.observation_count < 2 or len(set(self.source_learning_ids)) != self.observation_count:
            raise ValueError("live snapshot requires unique repeated verified observations")
        if not _power_of_two(self.predicted_context_tokens):
            raise ValueError("predicted context must be a bounded power-of-two bucket")
        if not 0 <= self.escalation_probability <= 1:
            raise ValueError("escalation probability must be normalized")
        if self.prewarm_escalation != (self.escalation_probability >= 0.75):
            raise ValueError("escalation prewarm threshold is not reproducible")
        if len(set(self.frequency_model_refs)) != len(self.frequency_model_refs):
            raise ValueError("frequency model preferences must be unique")
        if any(not value.strip() for value in self.frequency_model_refs):
            raise ValueError("frequency model references must not be empty")
        if (self.transition_model_ref is None) != (self.transition_confidence is None):
            raise ValueError("transition model and confidence must appear together")
        if self.transition_model_ref is not None:
            _text(self.transition_model_ref, "transition_model_ref")
            confidence = self.transition_confidence
            if confidence is None or not 0.5 <= confidence <= 1:
                raise ValueError("transition confidence is outside the live threshold")
        _digest(self.source_evidence_sha256)
        if not self.local_only or not self.advisory_only:
            raise ValueError("live adaptation cannot create authority or leave the device")


@dataclass(frozen=True, slots=True)
class ModelPrewarmReceipt:
    receipt_id: str
    snapshot_id: str
    candidate_model_ref: str
    source: ModelPrewarmSource
    status: ModelPrewarmStatus
    started_at: datetime
    completed_at: datetime
    reserved_bytes: int
    loaded_before: bool
    loaded_after: bool
    latency_ms: float
    reason_codes: tuple[str, ...]
    evicted_model_refs: tuple[str, ...] = ()
    local_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.receipt_id, "receipt_id"),
            (self.snapshot_id, "snapshot_id"),
            (self.candidate_model_ref, "candidate_model_ref"),
        ):
            _text(value, name)
        _time(self.started_at)
        _time(self.completed_at)
        if self.completed_at < self.started_at or self.latency_ms < 0:
            raise ValueError("prewarm timing is invalid")
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("prewarm receipt needs unique reason codes")
        if self.evicted_model_refs:
            raise ValueError("predictive prewarm cannot evict existing models")
        if self.status is ModelPrewarmStatus.REJECTED:
            if self.reserved_bytes != 0 or self.loaded_after != self.loaded_before:
                raise ValueError("rejected prewarm cannot reserve or change residency")
        elif self.reserved_bytes <= 0 or self.loaded_before:
            raise ValueError("executed prewarm needs a positive cold-model reservation")
        if self.status is ModelPrewarmStatus.COMPLETED and not self.loaded_after:
            raise ValueError("completed prewarm must prove model residency")
        if self.status is ModelPrewarmStatus.FAILED and self.loaded_after:
            raise ValueError("failed prewarm cannot claim model residency")
        if not self.local_only:
            raise ValueError("prewarm evidence must remain local")


def _power_of_two(value: int) -> bool:
    return 128 <= value <= 32_768 and value & (value - 1) == 0


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("live adaptation timestamps must be timezone-aware")


def _digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("live adaptation evidence requires lowercase SHA-256")
