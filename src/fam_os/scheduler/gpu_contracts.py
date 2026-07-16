"""Strict RAM/VRAM split placement and observed transfer-cost contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.scheduler.admission_contracts import (
    ADMISSION_CONTRACT_VERSION,
    AdmissionStatus,
    ResidentWeightEstimate,
)
from fam_os.scheduler.context_contracts import ContextMemoryEstimate
from fam_os.scheduler.live_contracts import SchedulerResourceObservation


GPU_PLACEMENT_CONTRACT_VERSION = "fam.scheduler.gpu-placement/v1alpha1"


@dataclass(frozen=True, slots=True)
class GpuPlacementRequest:
    request_id: str
    expert_id: str
    observation: SchedulerResourceObservation
    weight: ResidentWeightEstimate
    context: ContextMemoryEstimate
    accelerator_device_id: str
    model_layer_count: int
    requested_accelerator_layers: int
    main_accelerator_index: int
    contract_version: str = GPU_PLACEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != GPU_PLACEMENT_CONTRACT_VERSION:
            raise ValueError("unsupported GPU placement contract_version")
        for name in ("request_id", "expert_id", "accelerator_device_id"):
            _text(getattr(self, name), name)
        if self.weight.expert_id != self.expert_id:
            raise ValueError("GPU weight estimate references another expert")
        if self.context.contract_version != "fam.scheduler.context-memory/v1alpha1":
            raise ValueError("GPU request requires supported context estimate")
        if not self.context.model_resident_bytes_excluded:
            raise ValueError("GPU context must exclude model weights")
        if self.model_layer_count <= 0:
            raise ValueError("GPU model layer count must be positive")
        if not 0 <= self.requested_accelerator_layers <= self.model_layer_count:
            raise ValueError("requested accelerator layers exceed model")
        if self.main_accelerator_index < 0:
            raise ValueError("main accelerator index cannot be negative")
        if self.requested_accelerator_layers == 0:
            raise ValueError("GPU placement request requires accelerator layers")


@dataclass(frozen=True, slots=True)
class GpuPlacementDecision:
    decision_id: str
    request_id: str
    status: AdmissionStatus
    host_weight_compute_bytes: int
    accelerator_weight_bytes: int
    accelerator_context_bytes: int
    host_safety_reservation_bytes: int
    accelerator_reservation_bytes: int
    host_available_bytes: int
    accelerator_available_bytes: int
    estimated_transfer_bytes: int
    requested_accelerator_layers: int
    reason_codes: tuple[str, ...]
    admission_contract_version: str = ADMISSION_CONTRACT_VERSION
    contract_version: str = GPU_PLACEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != GPU_PLACEMENT_CONTRACT_VERSION:
            raise ValueError("unsupported GPU placement contract_version")
        if self.admission_contract_version != ADMISSION_CONTRACT_VERSION:
            raise ValueError("unsupported admission contract_version")
        _text(self.decision_id, "decision_id")
        _text(self.request_id, "request_id")
        values = (
            self.host_weight_compute_bytes, self.accelerator_weight_bytes,
            self.accelerator_context_bytes, self.host_safety_reservation_bytes,
            self.accelerator_reservation_bytes, self.host_available_bytes,
            self.accelerator_available_bytes, self.estimated_transfer_bytes,
            self.requested_accelerator_layers,
        )
        if any(value < 0 for value in values):
            raise ValueError("GPU placement values cannot be negative")
        if self.accelerator_reservation_bytes != self.accelerator_weight_bytes + self.accelerator_context_bytes:
            raise ValueError("GPU accelerator reservation is inconsistent")
        if self.estimated_transfer_bytes != self.accelerator_weight_bytes:
            raise ValueError("GPU transfer estimate must equal offloaded weights")
        if not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("GPU placement requires unique reason codes")
        fits = (
            self.host_safety_reservation_bytes <= self.host_available_bytes
            and self.accelerator_reservation_bytes <= self.accelerator_available_bytes
        )
        if self.status is AdmissionStatus.ADMITTED and not fits:
            raise ValueError("admitted GPU placement exceeds vector capacity")
        gate_reasons = {
            "resource_observation.degraded", "host_memory.not_authoritative",
            "accelerator.not_observed", "accelerator.not_available",
        }
        if self.status is AdmissionStatus.REJECTED and fits:
            if not gate_reasons.intersection(self.reason_codes):
                raise ValueError("rejected fitting GPU placement requires a safety gate")


@dataclass(frozen=True, slots=True)
class GpuPlacementEvidence:
    evidence_id: str
    request: GpuPlacementRequest
    decision: GpuPlacementDecision
    after_load_observation: SchedulerResourceObservation
    provider_resident_bytes: int
    provider_accelerator_bytes: int
    provider_host_compute_bytes: int
    provider_load_seconds: float
    effective_transfer_bytes_per_second: float
    service_memory_peak_bytes: int
    accelerator_memory_delta_bytes: int
    transfer_duration_includes_provider_load_overhead: bool
    placement_verified: bool
    output_sha256: str
    contract_version: str = GPU_PLACEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != GPU_PLACEMENT_CONTRACT_VERSION:
            raise ValueError("unsupported GPU placement contract_version")
        _text(self.evidence_id, "evidence_id")
        if self.decision.request_id != self.request.request_id:
            raise ValueError("GPU evidence decision references another request")
        if self.decision.status is not AdmissionStatus.ADMITTED:
            raise ValueError("GPU evidence requires an admitted placement")
        values = (
            self.provider_resident_bytes, self.provider_accelerator_bytes,
            self.provider_host_compute_bytes, self.service_memory_peak_bytes,
            self.accelerator_memory_delta_bytes,
        )
        if any(value < 0 for value in values):
            raise ValueError("GPU evidence bytes cannot be negative")
        if self.provider_host_compute_bytes != self.provider_resident_bytes - self.provider_accelerator_bytes:
            raise ValueError("GPU provider split is inconsistent")
        if self.provider_load_seconds <= 0 or self.effective_transfer_bytes_per_second <= 0:
            raise ValueError("GPU evidence requires positive load transfer cost")
        expected_rate = self.provider_accelerator_bytes / self.provider_load_seconds
        if abs(self.effective_transfer_bytes_per_second - expected_rate) > 1e-6:
            raise ValueError("GPU effective transfer rate is inconsistent")
        if not self.transfer_duration_includes_provider_load_overhead:
            raise ValueError("GPU evidence must disclose load-overhead timing basis")
        if not self.placement_verified or self.provider_accelerator_bytes <= 0:
            raise ValueError("GPU placement must be observed, not inferred")
        if self.provider_accelerator_bytes > self.decision.accelerator_reservation_bytes:
            raise ValueError("observed GPU allocation exceeds admitted reservation")
        if len(self.output_sha256) != 64:
            raise ValueError("GPU evidence requires output digest")
        if self.after_load_observation.previous_observation_id != self.request.observation.observation_id:
            raise ValueError("GPU evidence observations must be linked")


@dataclass(frozen=True, slots=True)
class FullWorkstationGpuReport:
    run_id: str
    started_at: datetime
    completed_at: datetime
    validation_profile_id: str
    effective_budget_id: str
    service_id: str
    evidences: tuple[GpuPlacementEvidence, ...]
    service_memory_peak_bytes: int
    service_cpu_usage_microseconds: int
    service_io_read_bytes: int
    service_io_write_bytes: int
    service_final_state: str
    final_loaded_model_refs: tuple[str, ...]
    contract_version: str = GPU_PLACEMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != GPU_PLACEMENT_CONTRACT_VERSION:
            raise ValueError("unsupported GPU placement contract_version")
        for name in ("run_id", "effective_budget_id", "service_id", "service_final_state"):
            _text(getattr(self, name), name)
        _time(self.started_at, "started_at")
        _time(self.completed_at, "completed_at")
        if self.completed_at <= self.started_at:
            raise ValueError("GPU report completion must follow start")
        if self.validation_profile_id != "full-reference-workstation":
            raise ValueError("GPU report requires full workstation profile")
        if len(self.evidences) < 4:
            raise ValueError("GPU report requires all reference inference experts")
        models = tuple(item.request.weight.runtime_artifact_id for item in self.evidences)
        if len(set(models)) != len(models):
            raise ValueError("GPU report evidence models must be unique")
        if not {"laguna-xs.2:q4_K_M", "gemma4:26b"} <= set(models):
            raise ValueError("GPU report must include both strong models")
        partial = sum(
            item.request.requested_accelerator_layers < item.request.model_layer_count
            and item.provider_host_compute_bytes > 0
            for item in self.evidences
        )
        if partial < 2:
            raise ValueError("GPU report must prove two real split-offloads")
        values = (
            self.service_memory_peak_bytes, self.service_cpu_usage_microseconds,
            self.service_io_read_bytes, self.service_io_write_bytes,
        )
        if any(value < 0 for value in values) or self.service_cpu_usage_microseconds <= 0:
            raise ValueError("GPU report resource counters are invalid")
        if self.service_final_state != "inactive" or self.final_loaded_model_refs:
            raise ValueError("GPU report requires inactive unloaded cleanup")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
