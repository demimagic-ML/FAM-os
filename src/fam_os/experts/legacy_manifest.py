"""Frozen v1alpha1 expert manifest retained for exact decoding and migration."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.experts.contracts import ExpertTier
from fam_os.experts.manifest import ExpertResourceRequirements
from fam_os.registry.package import PackageMetadata


LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION = "fam.expert.manifest/v1alpha1"


def _require_unique(name: str, values: tuple[str, ...], required: bool = True) -> None:
    if required and not values:
        raise ValueError(f"{name} must not be empty")
    if any(not value.strip() for value in values):
        raise ValueError(f"{name} values must not be empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} values must be unique")


@dataclass(frozen=True, slots=True)
class ExpertManifestV1Alpha1:
    """The immutable original manifest semantics from ADR 0016."""

    package: PackageMetadata
    expert_id: str
    display_name: str
    tier: ExpertTier
    capabilities: tuple[str, ...]
    runtime_contract_id: str
    artifact_ids: tuple[str, ...]
    resources: ExpertResourceRequirements
    required_verifier_ids: tuple[str, ...] = ()
    contract_version: str = LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in ("expert_id", "display_name", "runtime_contract_id"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.contract_version != LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION:
            raise ValueError("unsupported legacy expert manifest contract_version")
        _require_unique("capabilities", self.capabilities)
        _require_unique("artifact_ids", self.artifact_ids)
        _require_unique("required_verifier_ids", self.required_verifier_ids, required=False)
