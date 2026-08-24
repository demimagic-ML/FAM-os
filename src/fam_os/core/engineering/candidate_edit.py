"""Durable metadata-only records for authorized candidate edits."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, positive, text, texts
from fam_os.core.engineering.transactions import CandidateArtifact, CandidateOperation
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class CandidateEditStatus(StrEnum):
    INTENT_RECORDED = "intent_recorded"
    APPLIED = "applied"
    FAILED = "failed"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class CandidateEditRecord:
    edit_id: str
    definition_id: str
    task_id: str
    candidate_id: str
    session_id: str
    principal_id: str
    operation: CandidateOperation
    artifact: CandidateArtifact | None
    authorization_decision_ids: tuple[str, ...]
    changed_bytes: int
    status: CandidateEditStatus
    revision: int
    recorded_at: datetime
    updated_at: datetime
    after_sha256: str | None = None
    failure_code: str | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "edit_id", "definition_id", "task_id", "candidate_id",
            "session_id", "principal_id",
        ):
            text(getattr(self, name), name)
        texts(self.authorization_decision_ids, "authorization_decision_ids")
        positive(self.changed_bytes, "changed_bytes", allow_zero=True)
        positive(self.revision, "revision", allow_zero=True)
        aware(self.recorded_at, "recorded_at")
        aware(self.updated_at, "updated_at")
        digest(self.after_sha256, "after_sha256")
        if self.operation.artifact_id != (
            None if self.artifact is None else self.artifact.artifact_id
        ):
            raise ValueError("candidate edit artifact identity is mismatched")
        if self.status is CandidateEditStatus.APPLIED and self.failure_code is not None:
            raise ValueError("applied candidate edit cannot carry a failure")
        if self.status in {CandidateEditStatus.FAILED, CandidateEditStatus.RECOVERY_REQUIRED}:
            text(self.failure_code or "", "failure_code")
        elif self.failure_code is not None:
            raise ValueError("pending candidate edit cannot carry a failure")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate edit record version is unsupported")
