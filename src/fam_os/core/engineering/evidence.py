"""Approval checkpoint and aggregate engineering evidence contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import aware, digest, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class CheckpointDisposition(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class EngineeringOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CheckpointDecision:
    decision_id: str
    task_id: str
    proposal_id: str
    checkpoint_id: str
    decided_by: str
    decided_at: datetime
    disposition: CheckpointDisposition
    proposal_sha256: str
    reason: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "decision_id", "task_id", "proposal_id", "checkpoint_id",
            "decided_by", "reason",
        ):
            text(getattr(self, name), name)
        aware(self.decided_at, "decided_at")
        digest(self.proposal_sha256, "proposal_sha256", required=True)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("checkpoint decision contract version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringEvidence:
    evidence_id: str
    task_id: str
    recorded_at: datetime
    outcome: EngineeringOutcome
    snapshot_ids: tuple[str, ...]
    proposal_ids: tuple[str, ...]
    checkpoint_decision_ids: tuple[str, ...]
    tool_run_ids: tuple[str, ...]
    verifier_run_ids: tuple[str, ...]
    artifact_sha256: tuple[str, ...]
    changed_paths: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.evidence_id, "evidence_id")
        text(self.task_id, "task_id")
        aware(self.recorded_at, "recorded_at")
        for name in (
            "snapshot_ids", "proposal_ids", "checkpoint_decision_ids",
            "tool_run_ids", "verifier_run_ids", "changed_paths", "unresolved_risks",
        ):
            texts(getattr(self, name), name)
        for value in self.artifact_sha256:
            digest(value, "artifact_sha256 item", required=True)
        if self.outcome is EngineeringOutcome.SUCCEEDED and self.unresolved_risks:
            raise ValueError("successful engineering evidence cannot contain unresolved risks")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering evidence contract version is unsupported")
