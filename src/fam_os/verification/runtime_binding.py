"""Exact binding between a verifier package and its executable runtime."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.registry import ArtifactDigest
from fam_os.verification.manifest import VerifierManifest


VERIFIER_RUNTIME_BINDING_VERSION = "fam.verifier.runtime-binding/v1alpha1"


@dataclass(frozen=True, slots=True)
class VerifierRuntimeBinding:
    package_id: str
    package_version: str
    verifier_id: str
    runner_contract_id: str
    runtime_adapter_id: str
    entry_point: str
    expected_artifact_digest: ArtifactDigest
    contract_version: str = VERIFIER_RUNTIME_BINDING_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != VERIFIER_RUNTIME_BINDING_VERSION:
            raise ValueError("unsupported verifier runtime binding contract_version")
        for name in (
            "package_id", "package_version", "verifier_id", "runner_contract_id",
            "runtime_adapter_id", "entry_point",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if self.expected_artifact_digest.algorithm != "sha256":
            raise ValueError("verifier runtime binding requires SHA-256")


def validate_verifier_runtime_binding(
    manifest: VerifierManifest,
    binding: VerifierRuntimeBinding,
) -> None:
    package = manifest.package
    identity = (package.package_id, package.package_version, manifest.verifier_id)
    if identity != (binding.package_id, binding.package_version, binding.verifier_id):
        raise ValueError("runtime binding must identify the exact verifier package")
    if manifest.runner_contract_id != binding.runner_contract_id:
        raise ValueError("runtime binding contract must match verifier manifest")
    if package.artifact_digest != binding.expected_artifact_digest:
        raise ValueError("runtime binding digest must match package metadata")
