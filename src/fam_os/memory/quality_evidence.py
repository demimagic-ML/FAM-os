"""Retrieval quality and privacy evidence for the memory fabric."""

from dataclasses import dataclass

MEMORY_QUALITY_CONTRACT_VERSION = "fam.memory.quality-privacy/v1alpha1"


@dataclass(frozen=True, slots=True)
class MemoryQualityCase:
    query_id: str
    expected_document_id: str
    observed_document_id: str
    passed: bool


@dataclass(frozen=True, slots=True)
class MemoryQualityPrivacyReport:
    report_id: str
    cases: tuple[MemoryQualityCase, ...]
    top1_accuracy: float
    cross_owner_hit_count: int
    plaintext_leak_count: int
    passed: bool
    contract_version: str = MEMORY_QUALITY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("memory quality report requires cases")
        accuracy = sum(case.passed for case in self.cases) / len(self.cases)
        expected = accuracy >= .8 and self.cross_owner_hit_count == 0 and self.plaintext_leak_count == 0
        if abs(self.top1_accuracy - accuracy) > 1e-9 or self.passed != expected:
            raise ValueError("memory quality/privacy report does not derive from evidence")
