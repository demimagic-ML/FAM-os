"""Optimistic restart-safe resolution policy for independent reviews."""

from dataclasses import replace
from typing import Protocol

from fam_os.core.engineering.review import (
    EngineeringFindingDisposition,
    EngineeringReviewCheckpoint,
    EngineeringReviewResolutionReceipt,
    EngineeringReviewSelection,
    EngineeringReviewStatus,
    EngineeringReviewWaiverDecision,
    review_waiver_consequences_digest,
)


class EngineeringReviewStore(Protocol):
    def load(self, checkpoint_id: str) -> EngineeringReviewCheckpoint | None: ...
    def save(self, expected_revision: int, checkpoint: EngineeringReviewCheckpoint) -> None: ...
    def for_task(self, task_id: str) -> tuple[EngineeringReviewCheckpoint, ...]: ...
    def save_evidence(self, value, *, task_id: str | None = None) -> None: ...
    def load_evidence(self, evidence_id: str): ...
    def evidence_for_task(self, task_id: str) -> tuple[object, ...]: ...


class EngineeringReviewService:
    def __init__(self, store: EngineeringReviewStore) -> None:
        self._store = store

    def record(self, checkpoint: EngineeringReviewCheckpoint) -> None:
        existing = self._store.load(checkpoint.checkpoint_id)
        if existing is not None:
            if existing != checkpoint:
                raise RuntimeError("engineering review checkpoint identity conflicts")
            return
        selections = tuple(
            item for item in self._store.evidence_for_task(checkpoint.task_id)
            if isinstance(item, EngineeringReviewSelection)
            and item.candidate_id == checkpoint.candidate_id
            and item.changeset_sha256 == checkpoint.changeset_sha256
        )
        if (
            len(selections) != 1
            or selections[0].required_disciplines
            != checkpoint.required_disciplines
        ):
            raise PermissionError("engineering review lacks its exact policy selection")
        self._store.save(-1, checkpoint)

    def record_selection(self, selection: EngineeringReviewSelection) -> None:
        self._store.save_evidence(selection)

    def close(self) -> None:
        close = getattr(self._store, "close", None)
        if close is not None:
            close()

    def inspect(self, checkpoint_id: str) -> EngineeringReviewCheckpoint:
        return self._require(checkpoint_id)

    def for_task(self, task_id: str) -> tuple[EngineeringReviewCheckpoint, ...]:
        return self._store.for_task(task_id)

    def evidence_for_task(self, task_id: str) -> tuple[object, ...]:
        return self._store.evidence_for_task(task_id)

    def resolve(
        self, receipt: EngineeringReviewResolutionReceipt,
    ) -> EngineeringReviewCheckpoint:
        checkpoint = self._require(receipt.checkpoint_id)
        finding = _finding(checkpoint, receipt.finding_id)
        if finding.disposition is EngineeringFindingDisposition.RESOLVED:
            if finding.resolution_receipt_id == receipt.receipt_id:
                return checkpoint
            raise ValueError("engineering review finding is already resolved")
        if (
            receipt.task_id != checkpoint.task_id
            or receipt.candidate_id != checkpoint.candidate_id
            or receipt.changeset_sha256 != checkpoint.changeset_sha256
            or receipt.reviewer_id != checkpoint.reviewer_id
            or receipt.reviewer_independence_ref
            != checkpoint.reviewer_independence_ref
        ):
            raise PermissionError("review resolution is not bound to the checkpoint")
        self._store.save_evidence(receipt)
        return self._change(
            receipt.checkpoint_id, receipt.finding_id,
            EngineeringFindingDisposition.RESOLVED,
            receipt.receipt_id, receipt.resolved_at,
        )

    def waive(
        self, decision: EngineeringReviewWaiverDecision,
    ) -> EngineeringReviewCheckpoint:
        checkpoint = self._require(decision.checkpoint_id)
        findings = [
            item for item in checkpoint.findings
            if item.finding_id == decision.finding_id
        ]
        if (
            len(findings) != 1
            or decision.consequences_sha256
            != review_waiver_consequences_digest(checkpoint, findings[0])
        ):
            raise PermissionError("review waiver does not match exact consequences")
        finding = findings[0]
        if finding.disposition is EngineeringFindingDisposition.WAIVED:
            if finding.waiver_decision_id == decision.decision_id:
                return checkpoint
            raise ValueError("engineering review finding is already waived")
        self._store.save_evidence(decision, task_id=checkpoint.task_id)
        return self._change(
            decision.checkpoint_id, decision.finding_id,
            EngineeringFindingDisposition.WAIVED,
            decision.decision_id, decision.decided_at,
        )

    def require_passage(self, checkpoint_id: str) -> EngineeringReviewCheckpoint:
        checkpoint = self._require(checkpoint_id)
        if checkpoint.status is EngineeringReviewStatus.BLOCKED:
            raise PermissionError("independent engineering review is blocking")
        return checkpoint

    def inspect_evidence(self, evidence_id: str):
        value = self._store.load_evidence(evidence_id)
        if value is None:
            raise KeyError("engineering review evidence is unavailable")
        return value

    def _change(self, checkpoint_id, finding_id, disposition, evidence_id, instant):
        checkpoint = self._require(checkpoint_id)
        matches = [item for item in checkpoint.findings if item.finding_id == finding_id]
        if len(matches) != 1 or matches[0].disposition is not EngineeringFindingDisposition.OPEN:
            raise ValueError("engineering review finding is unavailable or already closed")
        findings = tuple(
            replace(
                item, disposition=disposition,
                resolution_receipt_id=(evidence_id if disposition is EngineeringFindingDisposition.RESOLVED else None),
                waiver_decision_id=(evidence_id if disposition is EngineeringFindingDisposition.WAIVED else None),
            ) if item.finding_id == finding_id else item
            for item in checkpoint.findings
        )
        status = (
            EngineeringReviewStatus.BLOCKED
            if any(item.disposition is EngineeringFindingDisposition.OPEN for item in findings)
            else EngineeringReviewStatus.WAIVED
            if any(item.disposition is EngineeringFindingDisposition.WAIVED for item in findings)
            else EngineeringReviewStatus.PASSED
        )
        updated = replace(
            checkpoint, findings=findings, status=status,
            completed_at=instant, revision=checkpoint.revision + 1,
        )
        self._store.save(checkpoint.revision, updated)
        return updated

    def _require(self, checkpoint_id):
        checkpoint = self._store.load(checkpoint_id)
        if checkpoint is None:
            raise KeyError("engineering review checkpoint is unavailable")
        return checkpoint


def _finding(checkpoint, finding_id):
    values = tuple(
        item for item in checkpoint.findings if item.finding_id == finding_id
    )
    if len(values) != 1:
        raise ValueError("engineering review finding is unavailable")
    return values[0]
