"""Versioned expert hardware/resource compatibility evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


EXPERT_COMPATIBILITY_CONTRACT_VERSION = "fam.expert.compatibility/v1alpha1"


class ExpertCompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    COMPATIBLE_CPU_ONLY = "compatible_cpu_only"
    CURRENTLY_CONSTRAINED = "currently_constrained"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True, slots=True)
class ExpertCompatibilityReport:
    package_id: str
    package_version: str
    expert_id: str
    inventory_id: str
    budget_id: str
    validation_profile_id: str
    status: ExpertCompatibilityStatus
    required_system_memory_bytes: int
    currently_available_system_memory_bytes: int
    compatible_storage_ids: tuple[str, ...]
    compatible_accelerator_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    contract_version: str = EXPERT_COMPATIBILITY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        names = (
            "package_id",
            "package_version",
            "expert_id",
            "inventory_id",
            "budget_id",
            "validation_profile_id",
        )
        if any(not getattr(self, name).strip() for name in names):
            raise ValueError("compatibility report identities must not be empty")
        if self.contract_version != EXPERT_COMPATIBILITY_CONTRACT_VERSION:
            raise ValueError("unsupported expert compatibility contract_version")
        if self.required_system_memory_bytes <= 0:
            raise ValueError("required system memory must be positive")
        if self.currently_available_system_memory_bytes < 0:
            raise ValueError("available system memory must not be negative")
        for name in ("compatible_storage_ids", "compatible_accelerator_ids", "reason_codes"):
            values = getattr(self, name)
            if len(set(values)) != len(values) or any(not item.strip() for item in values):
                raise ValueError(f"{name} values must be non-empty and unique")
        if self.status is ExpertCompatibilityStatus.COMPATIBLE and self.reason_codes:
            raise ValueError("fully compatible report cannot carry reason codes")
        if self.status is not ExpertCompatibilityStatus.COMPATIBLE and not self.reason_codes:
            raise ValueError("non-fully-compatible report requires reason codes")
