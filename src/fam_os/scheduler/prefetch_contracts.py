"""Resource-bounded predictive prefetch admission and execution evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.scheduler.cache_contracts import CacheEntryState, CacheTelemetrySnapshot
from fam_os.scheduler.prefetch_prediction import (
    PREFETCH_CONTRACT_VERSION,
    PrefetchPrediction,
    PrefetchPredictionRequest,
)


PREFETCH_POLICY_VERSION = "fam.scheduler.prefetch-admission/v1"


class PrefetchAdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class PrefetchResourceBudget:
    maximum_prefetch_bytes: int
    maximum_io_read_bytes: int
    available_tier_bytes: int
    host_available_bytes: int
    operating_system_reserve_bytes: int
    maximum_concurrent_prefetches: int
    maximum_waste_bytes: int
    current_waste_bytes: int

    def __post_init__(self) -> None:
        values = (
            self.maximum_prefetch_bytes, self.maximum_io_read_bytes,
            self.available_tier_bytes, self.host_available_bytes,
            self.operating_system_reserve_bytes, self.maximum_concurrent_prefetches,
            self.maximum_waste_bytes, self.current_waste_bytes,
        )
        if any(value < 0 for value in values) or self.maximum_concurrent_prefetches <= 0:
            raise ValueError("prefetch resource budget values are invalid")
        if self.current_waste_bytes > self.maximum_waste_bytes:
            raise ValueError("prefetch waste already exceeds its ceiling")


@dataclass(frozen=True, slots=True)
class PrefetchPolicyRequest:
    request_id: str
    prediction: PrefetchPrediction
    snapshot: CacheTelemetrySnapshot
    budget: PrefetchResourceBudget
    evaluated_at: datetime
    in_flight_prefetches: int
    eviction_permitted: bool
    policy_version: str = PREFETCH_POLICY_VERSION
    contract_version: str = PREFETCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PREFETCH_CONTRACT_VERSION or self.policy_version != PREFETCH_POLICY_VERSION:
            raise ValueError("unsupported prefetch policy version")
        _text(self.request_id, "request_id")
        _time(self.evaluated_at, "evaluated_at")
        if self.in_flight_prefetches < 0:
            raise ValueError("in-flight prefetch count cannot be negative")
        if self.eviction_permitted:
            raise ValueError("predictive prefetch cannot evict existing work")


@dataclass(frozen=True, slots=True)
class PrefetchPolicyDecision:
    decision_id: str
    request_id: str
    status: PrefetchAdmissionStatus
    reserved_prefetch_bytes: int
    reserved_io_read_bytes: int
    reasons: tuple[str, ...]
    selected_eviction_artifact_ids: tuple[str, ...]
    policy_version: str = PREFETCH_POLICY_VERSION
    contract_version: str = PREFETCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PREFETCH_CONTRACT_VERSION or self.policy_version != PREFETCH_POLICY_VERSION:
            raise ValueError("unsupported prefetch decision version")
        _text(self.decision_id, "decision_id")
        _text(self.request_id, "request_id")
        if not self.reasons or self.selected_eviction_artifact_ids:
            raise ValueError("prefetch decision needs reasons and cannot select evictions")
        admitted = self.status is PrefetchAdmissionStatus.ADMITTED
        if admitted != (self.reserved_prefetch_bytes > 0 and self.reserved_io_read_bytes > 0):
            raise ValueError("prefetch admission reservation is inconsistent")
        if not admitted and (self.reserved_prefetch_bytes or self.reserved_io_read_bytes):
            raise ValueError("rejected prefetch cannot reserve resources")


@dataclass(frozen=True, slots=True)
class PrefetchExecutionEvidence:
    evidence_id: str
    prediction: PrefetchPrediction
    decision: PrefetchPolicyDecision
    started_at: datetime
    completed_at: datetime
    requested_bytes: int
    prefetched_bytes: int
    demand_read_bytes: int
    prefetch_physical_read_bytes: int
    demand_physical_read_bytes: int
    cache_bytes_before: int
    cache_bytes_after: int
    prefetch_digest_sha256: str
    demand_digest_sha256: str
    used_before_expiry: bool
    temporary_artifact_removed: bool
    contract_version: str = PREFETCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PREFETCH_CONTRACT_VERSION:
            raise ValueError("unsupported prefetch evidence version")
        _text(self.evidence_id, "evidence_id")
        _time(self.started_at, "started_at")
        _time(self.completed_at, "completed_at")
        if self.completed_at <= self.started_at or self.completed_at > self.prediction.expires_at:
            raise ValueError("prefetch execution must finish inside prediction horizon")
        if self.decision.status is not PrefetchAdmissionStatus.ADMITTED:
            raise ValueError("only admitted prefetch can execute")
        if not 0 < self.requested_bytes == self.prefetched_bytes == self.demand_read_bytes:
            raise ValueError("prefetch execution byte counts are inconsistent")
        if self.prefetched_bytes > self.decision.reserved_prefetch_bytes:
            raise ValueError("prefetch execution exceeded reservation")
        if self.prefetch_physical_read_bytes < 0 or self.demand_physical_read_bytes != 0:
            raise ValueError("demand read was not served from warmed cache")
        if self.cache_bytes_after <= self.cache_bytes_before:
            raise ValueError("prefetch did not increase observed page cache")
        for digest in (self.prefetch_digest_sha256, self.demand_digest_sha256):
            _digest(digest)
        if self.prefetch_digest_sha256 != self.demand_digest_sha256:
            raise ValueError("prefetch and demand bytes differ")
        if not self.used_before_expiry or not self.temporary_artifact_removed:
            raise ValueError("canonical prefetch requires timely use and cleanup")


@dataclass(frozen=True, slots=True)
class PredictivePrefetchReport:
    report_id: str
    prediction_request: PrefetchPredictionRequest
    prediction: PrefetchPrediction
    admitted_request: PrefetchPolicyRequest
    admitted_decision: PrefetchPolicyDecision
    execution: PrefetchExecutionEvidence
    waste_guard_request: PrefetchPolicyRequest
    waste_guard_decision: PrefetchPolicyDecision
    contract_version: str = PREFETCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PREFETCH_CONTRACT_VERSION:
            raise ValueError("unsupported predictive prefetch report version")
        _text(self.report_id, "report_id")
        if getattr(self.prediction_request, "request_id", None) != self.prediction.request_id:
            raise ValueError("prefetch report prediction linkage is invalid")
        if self.admitted_request.prediction != self.prediction:
            raise ValueError("prefetch report admission uses another prediction")
        if self.admitted_decision.status is not PrefetchAdmissionStatus.ADMITTED:
            raise ValueError("prefetch report requires one admitted decision")
        if self.execution.decision != self.admitted_decision:
            raise ValueError("prefetch execution decision linkage is invalid")
        if self.waste_guard_decision.status is not PrefetchAdmissionStatus.REJECTED:
            raise ValueError("prefetch report requires a waste-guard rejection")
        if "budget.maximum_waste_exceeded" not in self.waste_guard_decision.reasons:
            raise ValueError("prefetch report must prove maximum-waste enforcement")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("prefetch digest must be lowercase SHA-256")
