"""Concrete validation-profile document and service-envelope contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.scheduler.configuration.policy import ValidationProfileConfiguration
from fam_os.scheduler.resources import (
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
)


VALIDATION_PROFILE_DOCUMENT_CONTRACT_VERSION = "fam.validation-profile/v1alpha1"
GIBIBYTE = 1024**3


class AcceleratorVisibility(StrEnum):
    DENY_ALL = "deny_all"
    DISCOVERED = "discovered"


class ValidationWorkloadMode(StrEnum):
    CPU_COMPATIBILITY = "cpu_compatibility"
    FULL_HOST = "full_host"


@dataclass(frozen=True, slots=True)
class ServiceResourceEnvelope:
    memory_max_bytes: int | None
    swap_max_bytes: int
    cpu_quota_cores: float | None
    accelerator_visibility: AcceleratorVisibility

    def __post_init__(self) -> None:
        if self.memory_max_bytes is not None and self.memory_max_bytes <= 0:
            raise ValueError("service memory maximum must be positive when provided")
        if self.swap_max_bytes < 0:
            raise ValueError("service swap maximum cannot be negative")
        if self.cpu_quota_cores is not None and self.cpu_quota_cores <= 0:
            raise ValueError("service CPU quota must be positive when provided")


@dataclass(frozen=True, slots=True)
class ValidationProfileDocument:
    document_id: str
    display_name: str
    description: str
    workload_mode: ValidationWorkloadMode
    configuration: ValidationProfileConfiguration
    service: ServiceResourceEnvelope
    contract_version: str = VALIDATION_PROFILE_DOCUMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("document_id", "display_name", "description"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if self.contract_version != VALIDATION_PROFILE_DOCUMENT_CONTRACT_VERSION:
            raise ValueError("unsupported validation-profile document contract_version")
        profile_id = self.configuration.profile.profile_id
        if profile_id == COMPAT_CPU_16GB_PROFILE_ID:
            self._validate_compatibility_profile()
        elif profile_id == FULL_REFERENCE_WORKSTATION_PROFILE_ID:
            self._validate_full_profile()

    @property
    def profile_id(self) -> str:
        return self.configuration.profile.profile_id

    def _validate_compatibility_profile(self) -> None:
        policy = self.configuration.policy
        if self.workload_mode is not ValidationWorkloadMode.CPU_COMPATIBILITY:
            raise ValueError("compat-cpu-16gb requires CPU compatibility workload mode")
        if self.service.memory_max_bytes != 16 * GIBIBYTE:
            raise ValueError("compat-cpu-16gb requires a 16 GiB service memory ceiling")
        if self.service.swap_max_bytes != 0 or policy.max_swap_bytes != 0:
            raise ValueError("compat-cpu-16gb requires zero service and scheduler swap")
        if self.service.accelerator_visibility is not AcceleratorVisibility.DENY_ALL:
            raise ValueError("compat-cpu-16gb must deny accelerator visibility")
        if policy.accelerator_allowed:
            raise ValueError("compat-cpu-16gb cannot allow accelerator placement")
        scheduler_cap = policy.max_memory_bytes
        if scheduler_cap is None:
            raise ValueError("compat-cpu-16gb requires a scheduler memory maximum")
        if scheduler_cap + policy.memory_headroom_bytes > 16 * GIBIBYTE:
            raise ValueError("compat scheduler limit and headroom exceed service ceiling")

    def _validate_full_profile(self) -> None:
        policy = self.configuration.policy
        if self.workload_mode is not ValidationWorkloadMode.FULL_HOST:
            raise ValueError("full-reference-workstation requires full-host workload mode")
        if self.service.accelerator_visibility is not AcceleratorVisibility.DISCOVERED:
            raise ValueError("full-reference-workstation requires discovered accelerators")
        if not policy.accelerator_allowed:
            raise ValueError("full-reference-workstation must allow accelerator placement")
        memory_cap = self.service.memory_max_bytes
        if memory_cap is not None and memory_cap <= 16 * GIBIBYTE:
            raise ValueError("full-reference-workstation cannot use a 16 GiB service ceiling")
