"""Durable owner-approved candidate transaction records."""

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum, StrEnum
import hashlib
import json

from fam_os.core.engineering._validation import aware, positive, text, texts
from fam_os.core.engineering.evidence import CheckpointDecision
from fam_os.core.engineering.transactions import (
    CandidateApplyReceipt, CandidateApplyStatus, CandidateArtifact,
    CandidateOperation, CandidateTransactionPreview,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class CandidateChangesetStatus(StrEnum):
    PREVIEWED = "previewed"
    APPLY_INTENT = "apply_intent"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    RECOVERY_REQUIRED = "recovery_required"
    ROLLBACK_INTENT = "rollback_intent"
    EXPLICITLY_ROLLED_BACK = "explicitly_rolled_back"
    ROLLBACK_RECOVERY_REQUIRED = "rollback_recovery_required"


@dataclass(frozen=True, slots=True)
class CandidateChangesetRecord:
    changeset_id: str
    definition_id: str
    task_id: str
    candidate_id: str
    preview: CandidateTransactionPreview
    operations: tuple[CandidateOperation, ...]
    artifacts: tuple[CandidateArtifact, ...]
    effect_authorization_decision_ids: tuple[str, ...]
    status: CandidateChangesetStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    decision: CheckpointDecision | None = None
    receipt: CandidateApplyReceipt | None = None
    failure_code: str | None = None
    rollback_decision: CheckpointDecision | None = None
    rollback_authorization_decision_ids: tuple[str, ...] = ()
    rollback_receipt: CandidateApplyReceipt | None = None
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("changeset_id", "definition_id", "task_id", "candidate_id"):
            text(getattr(self, name), name)
        texts(self.effect_authorization_decision_ids, "effect authorization decisions")
        texts(
            self.rollback_authorization_decision_ids,
            "rollback authorization decisions",
        )
        positive(self.revision, "revision", allow_zero=True)
        aware(self.created_at, "created_at")
        aware(self.updated_at, "updated_at")
        if (
            self.preview.transaction_id != self.changeset_id
            or self.preview.candidate_id != self.candidate_id
            or not self.operations
        ):
            raise ValueError("candidate changeset identities are mismatched")
        artifact_ids = {item.artifact_id for item in self.artifacts}
        if any(item.artifact_id is not None and item.artifact_id not in artifact_ids for item in self.operations):
            raise ValueError("candidate changeset operation artifact is unavailable")
        if self.status is not CandidateChangesetStatus.PREVIEWED and self.decision is None:
            raise ValueError("candidate apply state requires a checkpoint decision")
        if self.receipt is not None and self.receipt.transaction_id != self.changeset_id:
            raise ValueError("candidate changeset receipt identity is mismatched")
        expected = {
            CandidateChangesetStatus.APPLIED: CandidateApplyStatus.APPLIED,
            CandidateChangesetStatus.ROLLED_BACK: CandidateApplyStatus.ROLLED_BACK,
            CandidateChangesetStatus.RECOVERY_REQUIRED: CandidateApplyStatus.RECOVERY_REQUIRED,
        }.get(self.status)
        if expected is not None and (self.receipt is None or self.receipt.status is not expected):
            raise ValueError("candidate changeset status and receipt differ")
        if self.status in {CandidateChangesetStatus.PREVIEWED, CandidateChangesetStatus.APPLY_INTENT} and self.receipt is not None:
            raise ValueError("incomplete candidate changeset cannot claim a receipt")
        explicit = {
            CandidateChangesetStatus.ROLLBACK_INTENT,
            CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK,
            CandidateChangesetStatus.ROLLBACK_RECOVERY_REQUIRED,
        }
        if self.status in explicit and (
            self.receipt is None
            or self.receipt.status is not CandidateApplyStatus.APPLIED
            or self.rollback_decision is None
        ):
            raise ValueError("explicit rollback requires the successful apply receipt and decision")
        if (
            self.status is CandidateChangesetStatus.ROLLBACK_INTENT
            and self.rollback_receipt is not None
        ):
            raise ValueError("rollback intent cannot claim a completed rollback")
        if self.status is CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK and (
            self.rollback_receipt is None
            or self.rollback_receipt.status is not CandidateApplyStatus.ROLLED_BACK
            or not self.rollback_receipt.rollback_complete
        ):
            raise ValueError("explicit rollback receipt is incomplete")
        if self.status is CandidateChangesetStatus.ROLLBACK_RECOVERY_REQUIRED and (
            self.rollback_receipt is None
            or self.rollback_receipt.status
            is not CandidateApplyStatus.RECOVERY_REQUIRED
        ):
            raise ValueError("rollback recovery-required receipt is mismatched")
        if self.status not in explicit and any((
            self.rollback_decision is not None,
            bool(self.rollback_authorization_decision_ids),
            self.rollback_receipt is not None,
        )):
            raise ValueError("non-rollback changeset cannot claim explicit rollback state")
        if self.failure_code is not None:
            text(self.failure_code, "failure_code")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate changeset record version is unsupported")


def candidate_preview_digest(preview: CandidateTransactionPreview) -> str:
    return hashlib.sha256(json.dumps(
        _json_value(asdict(preview)), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def candidate_rollback_digest(
    record: CandidateChangesetRecord, expected_head_object_id: str,
) -> str:
    """Bind rollback approval to the applied transaction and exact Git head."""
    if (
        record.status
        not in {
            CandidateChangesetStatus.APPLIED,
            CandidateChangesetStatus.ROLLBACK_INTENT,
            CandidateChangesetStatus.EXPLICITLY_ROLLED_BACK,
            CandidateChangesetStatus.ROLLBACK_RECOVERY_REQUIRED,
        }
        or record.receipt is None
        or record.receipt.status is not CandidateApplyStatus.APPLIED
        or len(expected_head_object_id) not in {40, 64}
    ):
        raise ValueError("candidate rollback digest requires an applied changeset and Git head")
    int(expected_head_object_id, 16)
    value = {
        "task_id": record.task_id,
        "candidate_id": record.candidate_id,
        "changeset_id": record.changeset_id,
        "preview_sha256": candidate_preview_digest(record.preview),
        "apply_journal_sha256": record.receipt.journal_sha256,
        "applied_paths": record.receipt.applied_paths,
        "expected_head_object_id": expected_head_object_id,
    }
    return hashlib.sha256(json.dumps(
        _json_value(value), sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value
