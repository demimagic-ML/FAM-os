"""Versioned verifier package manifest contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from fam_os.registry import PackageMetadata


VERIFIER_MANIFEST_CONTRACT_VERSION = "fam.verifier.manifest/v1alpha1"


class DeterminismClass(StrEnum):
    DETERMINISTIC = "deterministic"
    BOUNDED_NONDETERMINISM = "bounded_nondeterminism"
    EXTERNAL_ATTESTATION = "external_attestation"


@dataclass(frozen=True, slots=True)
class VerifierManifest:
    package: PackageMetadata
    verifier_id: str
    display_name: str
    runner_contract_id: str
    acceptance_ids: tuple[str, ...]
    candidate_schema_ids: tuple[str, ...]
    evidence_schema_id: str
    determinism: DeterminismClass
    required_isolation_capabilities: tuple[str, ...]
    timeout_seconds: float
    network_access: bool = False
    contract_version: str = VERIFIER_MANIFEST_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "verifier_id",
            "display_name",
            "runner_contract_id",
            "evidence_schema_id",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.contract_version != VERIFIER_MANIFEST_CONTRACT_VERSION:
            raise ValueError("unsupported verifier manifest contract_version")
        self._require_unique("acceptance_ids", self.acceptance_ids)
        self._require_unique("candidate_schema_ids", self.candidate_schema_ids)
        self._require_unique(
            "required_isolation_capabilities", self.required_isolation_capabilities
        )
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if self.determinism is DeterminismClass.DETERMINISTIC and self.network_access:
            raise ValueError("deterministic verifiers cannot require network access")

    @staticmethod
    def _require_unique(name: str, values: tuple[str, ...]) -> None:
        if not values or any(not value.strip() for value in values):
            raise ValueError(f"{name} requires non-empty values")
        if len(set(values)) != len(values):
            raise ValueError(f"{name} values must be unique")
