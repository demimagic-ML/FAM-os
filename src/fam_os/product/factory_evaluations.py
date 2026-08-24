"""Owner-confirmed held-out evaluation authority for immutable adapters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fam_os.expert_factory import (
    FactoryEvaluationApproval,
    FactoryEvaluationPolicy,
    TrainingTerminalStatus,
    build_evaluation_approval,
)


class ProductFactoryEvaluationApprovals:
    def __init__(self, repositories, now=None) -> None:
        self._repositories = repositories
        self._now = now or (lambda: datetime.now(UTC))

    def approvals(self) -> tuple[FactoryEvaluationApproval, ...]:
        return self._repositories.factory_evaluations.approvals()

    def issue(
        self, *, request_id: str, training_receipt_id: str,
        incumbent_expert_id: str, incumbent_artifact_sha256: str,
        suite_sha256: str, evaluator_environment_sha256: str,
        evaluator_script_sha256: str, policy: FactoryEvaluationPolicy,
        one_use_evaluation_id: str, lifetime_seconds: int, confirmed: bool,
    ) -> FactoryEvaluationApproval:
        if not confirmed:
            raise PermissionError("evaluation approval requires confirmation")
        if not 60 <= lifetime_seconds <= 24 * 60 * 60:
            raise ValueError("evaluation approval lifetime must be 60 seconds to 24 hours")
        terminal = next(
            (
                item for item in self._repositories.training_jobs.terminals()
                if item.receipt_id == training_receipt_id
            ),
            None,
        )
        if terminal is None or terminal.status is not TrainingTerminalStatus.COMPLETED:
            raise PermissionError("evaluation requires completed immutable training")
        if (
            terminal.adapter_sha256 is None
            or terminal.adapter_config_sha256 is None
            or not terminal.base_weights_frozen
            or not terminal.network_denied
            or not terminal.held_out_absent
        ):
            raise PermissionError("training terminal evidence is not evaluation eligible")
        job = self._repositories.training_jobs.get(terminal.job_id)
        if job is None or job.approval_id != terminal.approval_id:
            raise RuntimeError("training terminal job lineage is unavailable")
        dataset = self._repositories.sealed_datasets.get(job.dataset_id)
        if dataset is None or dataset.manifest_sha256 != job.dataset_manifest_sha256:
            raise PermissionError("training dataset lineage changed")
        held_out = next(
            (
                item for item in self._repositories.sealed_datasets.blobs(dataset.dataset_id)
                if item.partition.value == "held_out"
            ),
            None,
        )
        if held_out is None:
            raise PermissionError("sealed held-out partition is unavailable")
        if policy.capability_id != job.capability_id:
            raise ValueError("evaluation policy capability does not match training")
        now = self._now()
        approval = build_evaluation_approval(
            approval_id=f"evaluation-approval-{request_id}",
            proposal_id=job.proposal_id, capability_id=job.capability_id,
            training_receipt_id=terminal.receipt_id,
            adapter_sha256=terminal.adapter_sha256,
            adapter_config_sha256=terminal.adapter_config_sha256,
            sealed_dataset_id=dataset.dataset_id,
            sealed_dataset_sha256=dataset.manifest_sha256,
            held_out_blob_id=held_out.blob_id,
            held_out_blob_sha256=held_out.plaintext_sha256,
            incumbent_expert_id=incumbent_expert_id,
            incumbent_artifact_sha256=incumbent_artifact_sha256,
            suite_sha256=suite_sha256,
            evaluator_environment_sha256=evaluator_environment_sha256,
            evaluator_script_sha256=evaluator_script_sha256, policy=policy,
            one_use_evaluation_id=one_use_evaluation_id, issued_at=now,
            expires_at=now + timedelta(seconds=lifetime_seconds),
        )
        if not self._repositories.factory_evaluations.add_approval(approval):
            existing = self._repositories.factory_evaluations.approval(
                approval.approval_id,
            )
            if existing != approval:
                raise RuntimeError("evaluation approval request identity was reused")
            return existing
        return approval
