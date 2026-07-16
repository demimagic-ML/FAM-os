"""In-memory trusted evidence lookup for final-result tests."""

from dataclasses import dataclass

from fam_os.core.contracts import DegradationNotice
from fam_os.core.lifecycle.final_contracts import (
    AcceptanceEvidenceRecord, CandidateEvidenceRecord,
)


@dataclass(frozen=True, slots=True)
class InMemoryFinalEvidenceRegistry:
    candidates: tuple[CandidateEvidenceRecord, ...] = ()
    acceptances: tuple[AcceptanceEvidenceRecord, ...] = ()
    degradations: tuple[DegradationNotice, ...] = ()

    def candidate(self, candidate_id):
        return next((item for item in self.candidates if item.candidate_id == candidate_id), None)

    def acceptance(self, evidence_id):
        return next((item for item in self.acceptances if item.evidence_id == evidence_id), None)

    def degradation(self, degradation_id):
        return next((item for item in self.degradations if item.degradation_id == degradation_id), None)
