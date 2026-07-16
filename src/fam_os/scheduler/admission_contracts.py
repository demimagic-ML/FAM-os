"""Replayable host-memory admission and stable eviction contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.scheduler.live_contracts import ObservationStatus
from fam_os.scheduler.residency_contracts import ExpertResidencyState


ADMISSION_CONTRACT_VERSION = "fam.scheduler.admission/v1alpha1"


class WeightEstimateSource(StrEnum):
    OBSERVED_WEIGHT_ONLY = "observed_weight_only"
    DECLARED_CONSERVATIVE = "declared_conservative"


class AdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ResidentWeightEstimate:
    expert_id: str
    runtime_artifact_id: str
    resident_weight_bytes: int
    source: WeightEstimateSource
    provenance: str
    context_bytes_excluded: bool = True

    def __post_init__(self) -> None:
        _text(self.expert_id, "expert_id")
        _text(self.runtime_artifact_id, "runtime_artifact_id")
        _text(self.provenance, "provenance")
        if self.resident_weight_bytes <= 0:
            raise ValueError("resident weight bytes must be positive")
        if not self.context_bytes_excluded:
            raise ValueError("resident weight estimate must exclude context bytes")


@dataclass(frozen=True, slots=True)
class EvictionCandidate:
    expert_id: str
    state: ExpertResidencyState
    reclaimable_bytes: int
    retention_priority: int
    last_used_at: datetime

    def __post_init__(self) -> None:
        _text(self.expert_id, "expert_id")
        _time(self.last_used_at, "last_used_at")
        if self.reclaimable_bytes < 0 or self.retention_priority < 0:
            raise ValueError("eviction candidate values cannot be negative")


@dataclass(frozen=True, slots=True)
class AdmissionRequest:
    request_id: str
    observation_id: str
    observation_status: ObservationStatus
    memory_scope_authoritative: bool
    available_memory_bytes: int
    residency_catalog_id: str
    residency_catalog_revision: int
    requested_expert_id: str
    requested_state: ExpertResidencyState
    weight: ResidentWeightEstimate
    context_estimate_id: str
    context_memory_bytes: int
    context_weights_excluded: bool
    eviction_candidates: tuple[EvictionCandidate, ...]
    contract_version: str = ADMISSION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != ADMISSION_CONTRACT_VERSION:
            raise ValueError("unsupported admission contract_version")
        for name in ("request_id", "observation_id", "residency_catalog_id", "requested_expert_id", "context_estimate_id"):
            _text(getattr(self, name), name)
        if self.available_memory_bytes < 0 or self.residency_catalog_revision < 0:
            raise ValueError("admission resource values cannot be negative")
        if self.requested_state not in (ExpertResidencyState.COLD, ExpertResidencyState.WARM):
            raise ValueError("admission only accepts cold or warm requested experts")
        if self.weight.expert_id != self.requested_expert_id:
            raise ValueError("weight estimate references another expert")
        if self.context_memory_bytes < 0 or not self.context_weights_excluded:
            raise ValueError("context estimate must exclude resident weights")
        identities = tuple(item.expert_id for item in self.eviction_candidates)
        if len(set(identities)) != len(identities):
            raise ValueError("eviction candidates must be unique")
        if self.requested_expert_id in identities:
            raise ValueError("requested expert cannot be an eviction candidate")


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    decision_id: str
    request_id: str
    status: AdmissionStatus
    weight_increment_bytes: int
    context_increment_bytes: int
    total_increment_bytes: int
    available_before_bytes: int
    reclaim_required_bytes: int
    eviction_expert_ids: tuple[str, ...]
    reclaimed_bytes: int
    available_after_bytes: int
    reason_codes: tuple[str, ...]
    contract_version: str = ADMISSION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != ADMISSION_CONTRACT_VERSION:
            raise ValueError("unsupported admission contract_version")
        _text(self.decision_id, "decision_id")
        _text(self.request_id, "request_id")
        values = (self.weight_increment_bytes, self.context_increment_bytes, self.total_increment_bytes, self.available_before_bytes, self.reclaim_required_bytes, self.reclaimed_bytes, self.available_after_bytes)
        if any(value < 0 for value in values):
            raise ValueError("admission decision bytes cannot be negative")
        if self.total_increment_bytes != self.weight_increment_bytes + self.context_increment_bytes:
            raise ValueError("admission increment is inconsistent")
        if len(set(self.eviction_expert_ids)) != len(self.eviction_expert_ids):
            raise ValueError("decision evictions must be unique")
        if len(set(self.reason_codes)) != len(self.reason_codes) or not self.reason_codes:
            raise ValueError("admission decision requires unique reasons")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
