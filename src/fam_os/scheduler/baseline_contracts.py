"""Strict evidence for the constrained 16 GiB CPU-only scheduler baseline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fam_os.scheduler.admission_contracts import AdmissionDecision, AdmissionStatus
from fam_os.scheduler.live_contracts import ObservationStatus, SchedulerResourceObservation


CPU_BASELINE_CONTRACT_VERSION = "fam.scheduler.cpu-baseline/v1alpha1"
COMPAT_PROFILE_ID = "compat-cpu-16gb"
GIB = 1024 ** 3
CPU_ONLY_ENVIRONMENT = (
    "CUDA_VISIBLE_DEVICES=-1",
    "GGML_VK_VISIBLE_DEVICES=-1",
    "OLLAMA_VULKAN=0",
    "OLLAMA_LLM_LIBRARY=cpu_avx2",
)


@dataclass(frozen=True, slots=True)
class CpuBaselineExpertAttempt:
    expert_id: str
    model_ref: str
    decision: AdmissionDecision
    inference_executed: bool
    output_sha256: str | None
    provider_resident_bytes: int | None
    provider_accelerator_bytes: int | None

    def __post_init__(self) -> None:
        _text(self.expert_id, "expert_id")
        _text(self.model_ref, "model_ref")
        admitted = self.decision.status is AdmissionStatus.ADMITTED
        if admitted != self.inference_executed:
            raise ValueError("only admitted baseline attempts may execute")
        if self.inference_executed:
            if self.output_sha256 is None or len(self.output_sha256) != 64:
                raise ValueError("executed baseline attempt requires output digest")
            if self.provider_resident_bytes is None or self.provider_resident_bytes <= 0:
                raise ValueError("executed baseline attempt requires resident bytes")
            if self.provider_accelerator_bytes != 0:
                raise ValueError("CPU baseline execution must report zero accelerator bytes")
        elif any(value is not None for value in (
            self.output_sha256, self.provider_resident_bytes,
            self.provider_accelerator_bytes,
        )):
            raise ValueError("rejected baseline attempt cannot claim execution evidence")


@dataclass(frozen=True, slots=True)
class CpuOnlyBaselineReport:
    run_id: str
    started_at: datetime
    completed_at: datetime
    validation_profile_id: str
    effective_budget_id: str
    service_id: str
    service_memory_limit_bytes: int
    scheduler_memory_limit_bytes: int
    operating_system_reserve_bytes: int
    service_memory_peak_bytes: int
    service_swap_limit_bytes: int
    service_swap_peak_bytes: int
    service_cpu_quota_cores: float
    service_cpu_usage_microseconds: int
    cpu_only_environment: tuple[str, ...]
    observations: tuple[SchedulerResourceObservation, ...]
    attempts: tuple[CpuBaselineExpertAttempt, ...]
    maximum_concurrent_loaded_model_refs: tuple[str, ...]
    oom_kill_count: int
    service_final_state: str
    final_loaded_model_refs: tuple[str, ...]
    contract_version: str = CPU_BASELINE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CPU_BASELINE_CONTRACT_VERSION:
            raise ValueError("unsupported CPU baseline contract_version")
        for name in ("run_id", "effective_budget_id", "service_id", "service_final_state"):
            _text(getattr(self, name), name)
        _time(self.started_at, "started_at")
        _time(self.completed_at, "completed_at")
        if self.completed_at <= self.started_at:
            raise ValueError("CPU baseline completion must follow start")
        if self.validation_profile_id != COMPAT_PROFILE_ID:
            raise ValueError("CPU baseline requires compatibility profile")
        self._validate_resources()
        self._validate_observations()
        self._validate_attempts()

    def _validate_resources(self) -> None:
        if self.service_memory_limit_bytes != 16 * GIB:
            raise ValueError("CPU baseline service ceiling must be exactly 16 GiB")
        if self.scheduler_memory_limit_bytes + self.operating_system_reserve_bytes > self.service_memory_limit_bytes:
            raise ValueError("CPU baseline scheduler plus reserve exceeds ceiling")
        if not 0 <= self.service_memory_peak_bytes <= self.service_memory_limit_bytes:
            raise ValueError("CPU baseline memory peak exceeds ceiling")
        if self.service_swap_limit_bytes != 0 or self.service_swap_peak_bytes != 0:
            raise ValueError("CPU baseline must neither allow nor consume swap")
        if self.service_cpu_quota_cores <= 0 or self.service_cpu_usage_microseconds <= 0:
            raise ValueError("CPU baseline requires bounded, observed CPU")
        if self.cpu_only_environment != CPU_ONLY_ENVIRONMENT:
            raise ValueError("CPU baseline environment does not deny accelerators")
        if self.oom_kill_count != 0:
            raise ValueError("CPU baseline cannot pass after an OOM kill")
        if self.service_final_state != "inactive" or self.final_loaded_model_refs:
            raise ValueError("CPU baseline requires inactive, unloaded cleanup")

    def _validate_observations(self) -> None:
        if len(self.observations) < 2:
            raise ValueError("CPU baseline requires repeated observations")
        for index, item in enumerate(self.observations):
            if item.validation_profile_id != self.validation_profile_id:
                raise ValueError("CPU baseline observation profile mismatch")
            if not item.memory.scope_authoritative or item.status is ObservationStatus.DEGRADED:
                raise ValueError("CPU baseline observations must be authoritative")
            if any(accelerator.placement_allowed for accelerator in item.accelerators):
                raise ValueError("CPU baseline observation permits accelerator placement")
            if index and item.previous_observation_id != self.observations[index - 1].observation_id:
                raise ValueError("CPU baseline observations must be linked")

    def _validate_attempts(self) -> None:
        if len(self.attempts) < 4:
            raise ValueError("CPU baseline requires executed and rejected experts")
        identities = tuple(item.expert_id for item in self.attempts)
        if len(set(identities)) != len(identities):
            raise ValueError("CPU baseline expert attempts must be unique")
        if sum(item.inference_executed for item in self.attempts) < 2:
            raise ValueError("CPU baseline requires a multi-expert execution")
        executed = {item.model_ref for item in self.attempts if item.inference_executed}
        concurrent = set(self.maximum_concurrent_loaded_model_refs)
        if len(concurrent) < 2 or not concurrent <= executed:
            raise ValueError("CPU baseline must prove concurrent executed residency")
        if len(concurrent) != len(self.maximum_concurrent_loaded_model_refs):
            raise ValueError("concurrent baseline model references must be unique")
        rejected = {item.model_ref for item in self.attempts if not item.inference_executed}
        if not {"laguna-xs.2:q4_K_M", "gemma4:26b"} <= rejected:
            raise ValueError("CPU baseline must explicitly reject both strong models")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _time(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
