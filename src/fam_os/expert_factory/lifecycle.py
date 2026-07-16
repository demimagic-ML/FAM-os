"""Auditable end-to-end Expert Factory lifecycle evidence."""

from dataclasses import dataclass

FACTORY_LIFECYCLE_CONTRACT_VERSION = "fam.factory.lifecycle/v1alpha1"


@dataclass(frozen=True, slots=True)
class FactoryLifecycleReport:
    report_id: str
    discovered: bool
    trained: bool
    hardware_objective_applied: bool
    quantized: bool
    signed: bool
    installed: bool
    selected: bool
    verified: bool
    retired: bool
    artifact_sha256: str
    package_manifest_sha256: str
    regression_gate_id: str
    passed: bool
    contract_version: str = FACTORY_LIFECYCLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        stages = (self.discovered, self.trained, self.hardware_objective_applied,
                  self.quantized, self.signed, self.installed, self.selected,
                  self.verified, self.retired)
        if self.passed != all(stages):
            raise ValueError("factory lifecycle pass requires every stage")
        if len(self.artifact_sha256) != 64 or len(self.package_manifest_sha256) != 64:
            raise ValueError("factory lifecycle requires SHA-256 artifacts")
