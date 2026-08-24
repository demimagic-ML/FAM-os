"""Content-free runtime health evidence for live adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.adaptation.control_contracts import LIVE_ADAPTATION_CONTROL_VERSION


@dataclass(frozen=True, slots=True)
class AdaptationRuntimeHealth:
    peak_temperature_c: float | None
    policy_conformant: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.peak_temperature_c is not None and not -20 <= self.peak_temperature_c <= 150:
            raise ValueError("adaptation runtime temperature is invalid")
        _reasons(self.reason_codes)


@dataclass(frozen=True, slots=True)
class AdaptationInferenceObservation:
    observation_id: str
    request_id: str
    snapshot_id: str
    workflow_id: str
    model_ref: str
    observed_at: datetime
    wall_seconds: float
    load_seconds: float
    prompt_tokens: int
    output_tokens: int
    context_tokens: int
    model_context_limit: int
    runtime_health: AdaptationRuntimeHealth
    local_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.observation_id, "observation_id"),
            (self.request_id, "request_id"),
            (self.snapshot_id, "snapshot_id"),
            (self.workflow_id, "workflow_id"),
            (self.model_ref, "model_ref"),
        ):
            _text(value, name)
        _time(self.observed_at)
        numeric = (self.wall_seconds, self.load_seconds, self.prompt_tokens, self.output_tokens)
        if any(value < 0 for value in numeric):
            raise ValueError("adaptation inference metrics must be nonnegative")
        if not 128 <= self.context_tokens <= self.model_context_limit <= 1_048_576:
            raise ValueError("adaptation inference context bounds are invalid")
        if not self.local_only:
            raise ValueError("adaptation inference observations must remain local")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class AdaptationHealthSample:
    sample_id: str
    observation_id: str
    request_id_sha256: str
    snapshot_id: str
    workflow_id: str
    model_ref: str
    observed_at: datetime
    verification_quality: float
    latency_seconds: float
    peak_temperature_c: float | None
    policy_conformant: bool
    reason_codes: tuple[str, ...]
    local_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        for value, name in (
            (self.sample_id, "sample_id"),
            (self.observation_id, "observation_id"),
            (self.snapshot_id, "snapshot_id"),
            (self.workflow_id, "workflow_id"),
            (self.model_ref, "model_ref"),
        ):
            _text(value, name)
        _digest(self.request_id_sha256)
        _time(self.observed_at)
        if not 0 <= self.verification_quality <= 1 or self.latency_seconds <= 0:
            raise ValueError("adaptation health quality or latency is invalid")
        _reasons(self.reason_codes)
        if not self.local_only:
            raise ValueError("adaptation health samples must remain local")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class AdaptationHealthSummary:
    snapshot_id: str
    workflow_id: str
    sample_count: int
    verification_quality: float
    p95_latency_seconds: float
    max_temperature_c: float | None
    thermal_sample_count: int
    policy_violation_count: int
    source_sample_ids: tuple[str, ...]
    source_evidence_sha256: str
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _text(self.workflow_id, "workflow_id")
        if self.sample_count < 2 or self.sample_count != len(self.source_sample_ids):
            raise ValueError("adaptation health summary requires repeated samples")
        if len(set(self.source_sample_ids)) != self.sample_count:
            raise ValueError("adaptation health summary samples must be unique")
        if not 0 <= self.verification_quality <= 1 or self.p95_latency_seconds <= 0:
            raise ValueError("adaptation health summary metrics are invalid")
        if not 0 <= self.thermal_sample_count <= self.sample_count:
            raise ValueError("adaptation thermal sample count is invalid")
        if self.policy_violation_count < 0 or self.policy_violation_count > self.sample_count:
            raise ValueError("adaptation policy violation count is invalid")
        if (self.max_temperature_c is None) != (self.thermal_sample_count == 0):
            raise ValueError("adaptation thermal evidence shape is invalid")
        _digest(self.source_evidence_sha256)
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class LiveAdaptationDriftReport:
    report_id: str
    workflow_id: str
    baseline: AdaptationHealthSummary
    candidate: AdaptationHealthSummary
    evaluated_dimensions: tuple[str, ...]
    unavailable_dimensions: tuple[str, ...]
    reason_codes: tuple[str, ...]
    drifted: bool
    evaluated_at: datetime
    local_only: bool = True
    contract_version: str = LIVE_ADAPTATION_CONTROL_VERSION

    def __post_init__(self) -> None:
        _text(self.report_id, "report_id")
        _text(self.workflow_id, "workflow_id")
        if self.baseline.workflow_id != self.workflow_id or self.candidate.workflow_id != self.workflow_id:
            raise ValueError("adaptation drift summaries must share one workflow")
        if self.baseline.snapshot_id == self.candidate.snapshot_id:
            raise ValueError("adaptation drift requires distinct snapshots")
        _dimensions(self.evaluated_dimensions, "evaluated", False)
        _dimensions(self.unavailable_dimensions, "unavailable", True)
        if set(self.evaluated_dimensions) & set(self.unavailable_dimensions):
            raise ValueError("adaptation drift dimensions cannot overlap")
        if self.drifted != bool(self.reason_codes):
            raise ValueError("adaptation drift flag must match reasons")
        if self.reason_codes:
            _reasons(self.reason_codes)
        _time(self.evaluated_at)
        if not self.local_only:
            raise ValueError("adaptation drift reports must remain local")
        _version(self.contract_version)


def _dimensions(values: tuple[str, ...], name: str, allow_empty: bool) -> None:
    if (not values and not allow_empty) or len(set(values)) != len(values):
        raise ValueError(f"{name} adaptation drift dimensions must be unique")
    for value in values:
        _text(value, f"{name}_dimension")


def _reasons(values: tuple[str, ...]) -> None:
    if not values or len(set(values)) != len(values):
        raise ValueError("adaptation health reasons must be unique")
    for value in values:
        _text(value, "reason_code")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("adaptation health timestamps must be timezone-aware")


def _digest(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("adaptation health evidence requires lowercase SHA-256")


def _version(value: str) -> None:
    if value != LIVE_ADAPTATION_CONTROL_VERSION:
        raise ValueError("unsupported live adaptation control version")
