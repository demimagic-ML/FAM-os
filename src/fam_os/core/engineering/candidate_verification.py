"""Durable receipt bundle for one signed candidate verification run."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, positive, text, texts
from fam_os.core.engineering.evidence import EngineeringEvidence
from fam_os.core.engineering.execution import EngineeringSandboxProfile, EngineeringToolReceipt
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class CandidateVerificationStatus(StrEnum):
    INTENT_RECORDED = "intent_recorded"
    COMPLETED = "completed"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class CandidateVerificationRecord:
    verification_id: str
    definition_id: str
    task_id: str
    candidate_id: str
    session_id: str
    principal_id: str
    toolchain: str
    recipe_id: str
    recipe_version: str
    profile: EngineeringSandboxProfile
    authorization_decision_ids: tuple[str, ...]
    status: CandidateVerificationStatus
    revision: int
    recorded_at: datetime
    updated_at: datetime
    receipt: EngineeringToolReceipt | None = None
    evidence: EngineeringEvidence | None = None
    passed: bool = False
    failure_code: str | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "verification_id", "definition_id", "task_id", "candidate_id",
            "session_id", "principal_id", "toolchain", "recipe_id",
            "recipe_version",
        ):
            text(getattr(self, name), name)
        texts(self.authorization_decision_ids, "authorization_decision_ids")
        positive(self.revision, "revision", allow_zero=True)
        aware(self.recorded_at, "recorded_at")
        aware(self.updated_at, "updated_at")
        if self.status is CandidateVerificationStatus.COMPLETED:
            if self.receipt is None or self.evidence is None:
                raise ValueError("completed candidate verification requires receipts")
            if (
                self.receipt.task_id != self.task_id
                or self.receipt.candidate_id != self.candidate_id
                or self.receipt.recipe_id != self.recipe_id
                or self.evidence.task_id != self.task_id
                or self.receipt.receipt_id not in self.evidence.tool_run_ids
            ):
                raise ValueError("candidate verification receipt identities differ")
            if self.passed != (self.evidence.outcome.value == "succeeded"):
                raise ValueError("candidate verification result and evidence differ")
        elif self.receipt is not None or self.evidence is not None or self.passed:
            raise ValueError("incomplete candidate verification cannot claim receipts")
        if self.status is CandidateVerificationStatus.RECOVERY_REQUIRED:
            text(self.failure_code or "", "failure_code")
        elif self.failure_code is not None:
            raise ValueError("candidate verification failure code is invalid")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate verification record version is unsupported")
