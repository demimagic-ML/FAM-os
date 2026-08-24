"""Trusted evidence lookup ports for final result policy."""

from typing import Protocol

from fam_os.core.contracts import DegradationNotice
from fam_os.core.lifecycle.final_contracts import (
    AcceptanceEvidenceRecord, CandidateEvidenceRecord,
)
from fam_os.fabric import RemoteExecutionEvidence, RemoteRecoveryEvidence


class FinalEvidenceRegistry(Protocol):
    def candidate(self, candidate_id: str) -> CandidateEvidenceRecord | None: ...

    def acceptance(self, evidence_id: str) -> AcceptanceEvidenceRecord | None: ...

    def degradation(self, degradation_id: str) -> DegradationNotice | None: ...

    def remote_execution(
        self,
        evidence_id: str,
    ) -> RemoteExecutionEvidence | None: ...

    def remote_recovery(
        self,
        evidence_id: str,
    ) -> RemoteRecoveryEvidence | None: ...
