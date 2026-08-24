"""Receipt-driven Core coordinator for master engineering-loop transitions."""

from datetime import datetime
from collections.abc import Callable

from fam_os.core.engineering.evidence import (
    CheckpointDecision, CheckpointDisposition, EngineeringEvidence,
    EngineeringOutcome,
)
from fam_os.core.engineering.git_delivery import (
    GitLocalAction, GitLocalActionKind, GitLocalActionReceipt,
    GitPublicationApproval, GitPublicationReceipt,
)
from fam_os.core.engineering.database import (
    DatabaseChangePlan, DatabaseChangeStatus, DatabasePostapplyReceipt,
    DatabaseVerificationReceipt,
)
from fam_os.core.engineering.master_loop import EngineeringLoopStage, MasterEngineeringLoop
from fam_os.core.engineering.repository.planning import ArchitectureProposal, RepositoryAnalysis
from fam_os.core.engineering.transactions import (
    CandidateApplyReceipt, CandidateApplyStatus, CandidateTransactionPreview,
    CandidateWorkspace,
)


class EngineeringLifecycleDriver:
    """Advance lifecycle state only from exact typed service outputs."""

    def __init__(
        self, loop: MasterEngineeringLoop,
        grant_validator: Callable[[str, str, datetime], None],
        publication_grant_validator: Callable[[GitPublicationApproval], None]
        | None = None,
    ) -> None:
        self._loop = loop
        self._grant_validator = grant_validator
        self._publication_grant_validator = publication_grant_validator

    def _authorize(self, task_id: str, instant: datetime):
        state = self._loop.state(task_id)
        self._grant_validator(task_id, state.grant_id, instant)
        return state

    def record_inspection(self, analysis: RepositoryAnalysis) -> None:
        self._authorize(analysis.task_id, analysis.completed_at)
        self._loop.advance(
            analysis.task_id, EngineeringLoopStage.INSPECTED,
            analysis.analysis_id, instant=analysis.completed_at,
        )

    def record_architecture(self, proposal: ArchitectureProposal) -> None:
        state = self._authorize(proposal.task_id, proposal.created_at)
        if proposal.analysis_id != state.repository_evidence_id:
            raise ValueError("architecture proposal is not based on the recorded analysis")
        self._loop.advance(
            proposal.task_id, EngineeringLoopStage.PROPOSED,
            proposal.proposal_id, instant=proposal.created_at,
        )

    def record_candidate(self, candidate: CandidateWorkspace) -> None:
        self._authorize(candidate.task_id, candidate.created_at)
        self._loop.advance(
            candidate.task_id, EngineeringLoopStage.CANDIDATE_READY,
            candidate.candidate_id, instant=candidate.created_at,
        )

    def record_preparation(
        self,
        analysis: RepositoryAnalysis,
        proposal: ArchitectureProposal,
        candidate: CandidateWorkspace,
    ) -> None:
        if (
            proposal.task_id != analysis.task_id
            or proposal.analysis_id != analysis.analysis_id
            or candidate.task_id != analysis.task_id
        ):
            raise ValueError("engineering preparation receipts are mismatched")
        self._authorize(analysis.task_id, candidate.created_at)
        self._loop.advance_batch(analysis.task_id, (
            (EngineeringLoopStage.INSPECTED, analysis.analysis_id,
             analysis.completed_at, {}, None),
            (EngineeringLoopStage.PROPOSED, proposal.proposal_id,
             proposal.created_at, {}, None),
            (EngineeringLoopStage.CANDIDATE_READY, candidate.candidate_id,
             candidate.created_at, {}, None),
        ))

    def preparation_is_recorded(
        self,
        analysis: RepositoryAnalysis,
        proposal: ArchitectureProposal,
        candidate: CandidateWorkspace,
    ) -> bool:
        """Recognize only the exact atomically recorded preparation sequence."""
        state = self._loop.state(analysis.task_id)
        return (
            state.stage is EngineeringLoopStage.CANDIDATE_READY
            and state.repository_evidence_id == analysis.analysis_id
            and state.architecture_proposal_id == proposal.proposal_id
            and state.candidate_id == candidate.candidate_id
        )

    def record_verification(
        self, evidence: EngineeringEvidence,
        *, additional_budget: dict[str, int] | None = None,
    ) -> None:
        _successful(evidence)
        state = self._authorize(evidence.task_id, evidence.recorded_at)
        if state.candidate_id is None:
            raise ValueError("verification lacks a recorded candidate")
        budget = {"used_commands": len(evidence.tool_run_ids)}
        for name, value in (additional_budget or {}).items():
            budget[name] = budget.get(name, 0) + value
        if state.stage is EngineeringLoopStage.CANDIDATE_READY:
            self._loop.advance(
                evidence.task_id, EngineeringLoopStage.VERIFIED,
                evidence.evidence_id, instant=evidence.recorded_at,
                budget_delta=budget,
            )
            return
        if state.stage is EngineeringLoopStage.VERIFIED:
            self._loop.record_additional_verification(
                evidence.task_id, evidence.evidence_id,
                instant=evidence.recorded_at, budget_delta=budget,
            )
            return
        raise ValueError("candidate verification occurs at an invalid lifecycle stage")

    def record_database_verification(
        self, plan: DatabaseChangePlan, receipt: DatabaseVerificationReceipt,
    ) -> None:
        state = self._authorize(plan.task_id, receipt.completed_at)
        if (
            plan.candidate_id != state.candidate_id
            or receipt.plan_id != plan.plan_id
            or receipt.target_id != plan.target.target_id
            or receipt.status is not DatabaseChangeStatus.VERIFIED
            or receipt.applied_step_ids
            != tuple(item.step_id for item in plan.migration_steps)
            or receipt.postcondition_ids != plan.postcondition_ids
        ):
            raise ValueError("database verification is not exact and successful")
        self._loop.record_database_verification(
            plan.task_id, receipt.receipt_id, instant=receipt.completed_at,
            budget_delta={"used_commands": 1},
        )

    def record_database_reverification(
        self, plan: DatabaseChangePlan, prior: DatabaseVerificationReceipt,
        receipt: DatabasePostapplyReceipt,
    ) -> None:
        self._authorize(receipt.task_id, receipt.observed_at)
        if (
            receipt.task_id != plan.task_id
            or receipt.plan_id != plan.plan_id
            or receipt.target_id != plan.target.target_id
            or receipt.changeset_id != plan.approved_changeset_id
            or receipt.verification_receipt_id != prior.receipt_id
            or receipt.schema_sha256 != prior.schema_sha256
            or receipt.data_sha256 != prior.data_sha256
            or not receipt.passed
        ):
            raise ValueError("database post-apply evidence is not exact and passing")
        self._loop.record_database_reverification(
            plan.task_id, receipt.receipt_id, instant=receipt.observed_at,
        )

    def request_changeset_checkpoint(
        self, task_id: str, preview: CandidateTransactionPreview,
    ) -> None:
        state = self._authorize(task_id, preview.generated_at)
        if preview.candidate_id != state.candidate_id:
            raise ValueError("changeset preview targets a different candidate")
        trusted = {
            *state.verification_receipt_ids,
            *state.runtime_diagnostic_receipt_ids,
            *state.database_receipt_ids,
            *state.integration_environment_receipt_ids,
        }
        if not set(preview.verification_evidence_ids).issubset(trusted):
            raise ValueError("changeset preview lacks recorded verification evidence")
        self._loop.advance(
            task_id, EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED,
            preview.transaction_id, instant=preview.generated_at,
        )

    def record_apply(
        self,
        task_id: str,
        receipt: CandidateApplyReceipt,
        decision: CheckpointDecision,
    ) -> None:
        state = self._authorize(task_id, receipt.completed_at)
        if (
            decision.task_id != task_id
            or decision.checkpoint_id != state.pending_changeset_id
            or receipt.transaction_id != state.pending_changeset_id
            or receipt.candidate_id != state.candidate_id
            or receipt.status is not CandidateApplyStatus.APPLIED
            or decision.disposition is not CheckpointDisposition.APPROVED
        ):
            raise PermissionError("apply receipt or checkpoint decision is not exact")
        self._loop.advance(
            task_id, EngineeringLoopStage.APPLIED,
            f"apply:{receipt.journal_sha256}", instant=receipt.completed_at,
            checkpoint_id=decision.checkpoint_id,
            budget_delta={"used_files": len(receipt.applied_paths)},
        )

    def record_reverification(self, evidence: EngineeringEvidence) -> None:
        _successful(evidence)
        state = self._authorize(evidence.task_id, evidence.recorded_at)
        budget = {"used_commands": len(evidence.tool_run_ids)}
        if state.stage is EngineeringLoopStage.APPLIED:
            self._loop.advance(
                evidence.task_id, EngineeringLoopStage.REVERIFIED,
                evidence.evidence_id, instant=evidence.recorded_at,
                budget_delta=budget,
            )
            return
        if state.stage is EngineeringLoopStage.REVERIFIED:
            self._loop.record_additional_reverification(
                evidence.task_id, evidence.evidence_id,
                instant=evidence.recorded_at, budget_delta=budget,
            )
            return
        raise ValueError("reverification requires applied or reverified state")

    def record_commit(
        self, task_id: str, action: GitLocalAction,
        receipt: GitLocalActionReceipt,
    ) -> None:
        self._authorize(task_id, receipt.completed_at)
        if (
            action.task_id != task_id
            or action.kind is not GitLocalActionKind.COMMIT
            or receipt.action_id != action.action_id
            or receipt.after_object_id is None
        ):
            raise ValueError("Git commit receipt is not exact")
        self._loop.advance(
            task_id, EngineeringLoopStage.COMMITTED,
            receipt.receipt_id, instant=receipt.completed_at,
            budget_delta={"used_commands": 1},
        )

    def request_publication(self, approval: GitPublicationApproval) -> None:
        state = self._authorize(approval.task_id, approval.approved_at)
        if approval.grant_id != state.grant_id:
            if self._publication_grant_validator is None:
                raise PermissionError("publication approval uses a different grant")
            self._publication_grant_validator(approval)
        self._loop.advance(
            approval.task_id, EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED,
            approval.approval_id, instant=approval.approved_at,
        )

    def record_publication(
        self, task_id: str, receipt: GitPublicationReceipt,
    ) -> None:
        state = self._authorize(task_id, receipt.completed_at)
        if receipt.approval_id != state.pending_publication_id:
            raise PermissionError("publication receipt is not for the pending approval")
        self._loop.advance(
            task_id, EngineeringLoopStage.PUBLISHED,
            receipt.receipt_id, instant=receipt.completed_at,
            checkpoint_id=receipt.approval_id,
            budget_delta={"used_commands": 1},
        )

    def record_rollback(
        self, task_id: str, receipt: CandidateApplyReceipt,
        git_action: GitLocalAction | None = None,
        git_receipt: GitLocalActionReceipt | None = None,
    ) -> None:
        state = self._authorize(task_id, receipt.completed_at)
        if (
            receipt.candidate_id != state.candidate_id
            or receipt.status is not CandidateApplyStatus.ROLLED_BACK
            or not receipt.rollback_complete
        ):
            raise ValueError("rollback receipt is incomplete or mismatched")
        if state.stage is EngineeringLoopStage.COMMITTED and (
            git_action is None
            or git_receipt is None
            or git_action.task_id != task_id
            or git_action.kind is not GitLocalActionKind.COMMIT
            or git_receipt.action_id != git_action.action_id
            or git_receipt.after_object_id is None
        ):
            raise ValueError("committed rollback requires an exact inverse Git commit")
        if state.stage is not EngineeringLoopStage.COMMITTED and any((
            git_action is not None, git_receipt is not None,
        )):
            raise ValueError("pre-commit rollback cannot claim a Git receipt")
        evidence_id = f"rollback:{receipt.journal_sha256}"
        budget = None
        if git_receipt is not None:
            evidence_id += f":{git_receipt.receipt_id}"
            budget = {"used_commands": 1}
        self._loop.advance(
            task_id, EngineeringLoopStage.ROLLED_BACK,
            evidence_id, instant=(
                git_receipt.completed_at if git_receipt is not None
                else receipt.completed_at
            ),
            budget_delta=budget,
        )

    def complete(self, evidence: EngineeringEvidence) -> None:
        _successful(evidence)
        self._authorize(evidence.task_id, evidence.recorded_at)
        self._loop.advance(
            evidence.task_id, EngineeringLoopStage.COMPLETED,
            evidence.evidence_id, instant=evidence.recorded_at,
        )


def _successful(evidence: EngineeringEvidence) -> None:
    if evidence.outcome is not EngineeringOutcome.SUCCEEDED:
        raise ValueError("engineering lifecycle requires successful evidence")
