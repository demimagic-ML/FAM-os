"""Trusted evidence lookup ports for final result policy."""

from typing import Protocol

from fam_os.core.contracts import DegradationNotice
from fam_os.core.lifecycle.final_contracts import (
    AcceptanceEvidenceRecord, CandidateEvidenceRecord,
)


class FinalEvidenceRegistry(Protocol):
    def candidate(self, candidate_id: str) -> CandidateEvidenceRecord | None: ...

    def acceptance(self, evidence_id: str) -> AcceptanceEvidenceRecord | None: ...

    def degradation(self, degradation_id: str) -> DegradationNotice | None: ...
