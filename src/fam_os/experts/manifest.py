"""Versioned installable expert manifest contracts."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.experts.capabilities import require_expert_capabilities
from fam_os.experts.contracts import ExpertTier
from fam_os.registry.package import PackageMetadata


EXPERT_MANIFEST_CONTRACT_VERSION = "fam.expert.manifest/v1alpha2"


def _require_unique(name: str, values: tuple[str, ...], required: bool = True) -> None:
    if required and not values:
        raise ValueError(f"{name} must not be empty")
    if any(not value.strip() for value in values):
        raise ValueError(f"{name} values must not be empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} values must be unique")


@dataclass(frozen=True, slots=True)
class ExpertResourceRequirements:
    estimated_resident_bytes: int
    storage_bytes: int
    max_context_tokens: int
    minimum_system_memory_bytes: int = 0
    minimum_accelerator_memory_bytes: int = 0
    accelerator_optional: bool = True
    supported_architectures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.estimated_resident_bytes,
            self.storage_bytes,
            self.max_context_tokens,
            self.minimum_system_memory_bytes,
            self.minimum_accelerator_memory_bytes,
        )
        if any(value < 0 for value in values):
            raise ValueError("expert resource requirements cannot be negative")
        if self.estimated_resident_bytes == 0 or self.max_context_tokens == 0:
            raise ValueError("resident bytes and max context tokens must be positive")
        if not self.accelerator_optional and self.minimum_accelerator_memory_bytes == 0:
            raise ValueError("required acceleration needs a positive accelerator memory minimum")
        _require_unique("supported_architectures", self.supported_architectures, required=False)


@dataclass(frozen=True, slots=True)
class ExpertManifest:
    package: PackageMetadata
    expert_id: str
    display_name: str
    tier: ExpertTier
    capabilities: tuple[str, ...]
    runtime_contract_id: str
    artifact_ids: tuple[str, ...]
    resources: ExpertResourceRequirements
    required_verifier_ids: tuple[str, ...] = ()
    contract_version: str = EXPERT_MANIFEST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in ("expert_id", "display_name", "runtime_contract_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.contract_version != EXPERT_MANIFEST_CONTRACT_VERSION:
            raise ValueError("unsupported expert manifest contract_version")
        require_expert_capabilities(
            self.capabilities,
            publisher_id=self.package.publisher_id,
        )
        _require_unique("artifact_ids", self.artifact_ids)
        _require_unique("required_verifier_ids", self.required_verifier_ids, required=False)
