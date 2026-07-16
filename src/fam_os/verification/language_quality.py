"""Provider-neutral reports for compiler and test based language verifiers."""

from dataclasses import dataclass
from enum import StrEnum


LANGUAGE_QUALITY_CONTRACT_VERSION = "fam.verifier.language-quality/v1alpha1"


class LanguageGateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class LanguageGateEvidence:
    gate_id: str
    status: LanguageGateStatus
    exit_code: int | None
    output: str


@dataclass(frozen=True, slots=True)
class LanguageQualityReport:
    verification_id: str
    language_id: str
    toolchain_version: str
    gates: tuple[LanguageGateEvidence, ...]
    contract_version: str = LANGUAGE_QUALITY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.verification_id.strip() or not self.language_id.strip():
            raise ValueError("verification and language IDs must not be empty")
        if not self.toolchain_version.strip() or not self.gates:
            raise ValueError("toolchain version and gates are required")
        if len({gate.gate_id for gate in self.gates}) != len(self.gates):
            raise ValueError("language gate IDs must be unique")

    @property
    def passed(self) -> bool:
        return all(gate.status is LanguageGateStatus.PASSED for gate in self.gates)
