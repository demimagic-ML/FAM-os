"""Phase 11 local-adaptation exit evidence."""

from dataclasses import dataclass

PHASE11_EXIT_CONTRACT_VERSION = "fam.adaptation.phase11-exit/v1alpha1"


@dataclass(frozen=True, slots=True)
class Phase11ExitEvidence:
    evidence_id: str
    model_ref: str
    baseline_latency_seconds: float
    adapted_latency_seconds: float
    baseline_verified: bool
    adapted_verified: bool
    user_reset_preserved: bool
    improved: bool
    passed: bool
    contract_version: str = PHASE11_EXIT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected_improved = self.adapted_latency_seconds < self.baseline_latency_seconds
        expected = expected_improved and self.baseline_verified and self.adapted_verified
        expected = expected and self.user_reset_preserved
        if self.improved != expected_improved or self.passed != expected:
            raise ValueError("Phase 11 exit must derive from measured repeated workflow")
