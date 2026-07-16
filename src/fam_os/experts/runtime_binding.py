"""Provider-neutral binding from an expert package artifact to a local runtime."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.experts.manifest import ExpertManifest
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry.package import ArtifactDigest


EXPERT_RUNTIME_BINDING_VERSION = "fam.expert.runtime-binding/v1alpha1"


@dataclass(frozen=True, slots=True)
class ExpertRuntimeBinding:
    coordinate: ExpertPackageCoordinate
    expert_id: str
    runtime_contract_id: str
    runtime_adapter_id: str
    artifact_id: str
    artifact_ref: str
    expected_artifact_digest: ArtifactDigest
    contract_version: str = EXPERT_RUNTIME_BINDING_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != EXPERT_RUNTIME_BINDING_VERSION:
            raise ValueError("unsupported expert runtime binding contract_version")
        for name in (
            "expert_id", "runtime_contract_id", "runtime_adapter_id",
            "artifact_id", "artifact_ref",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if self.expected_artifact_digest.algorithm != "sha256":
            raise ValueError("runtime artifact binding requires SHA-256")


def validate_runtime_binding(manifest: ExpertManifest, binding: ExpertRuntimeBinding) -> None:
    package = manifest.package
    coordinate = ExpertPackageCoordinate(package.package_id, package.package_version)
    if coordinate != binding.coordinate or manifest.expert_id != binding.expert_id:
        raise ValueError("runtime binding must identify the exact expert package")
    if manifest.runtime_contract_id != binding.runtime_contract_id:
        raise ValueError("runtime binding contract must match the expert manifest")
    if binding.artifact_id not in manifest.artifact_ids:
        raise ValueError("runtime binding artifact must be declared by the manifest")
    if package.artifact_digest != binding.expected_artifact_digest:
        raise ValueError("runtime binding digest must match package metadata")
