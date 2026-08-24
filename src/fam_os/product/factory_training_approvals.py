"""Owner-confirmed six-dimensional authority for one real training job."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fam_os.expert_factory import (
    AdapterTrainingRecipe,
    ApprovedBaseModel,
    FactoryTrainingApproval,
    TrainingResourceBudget,
)


class ProductFactoryTrainingApprovals:
    def __init__(self, repositories, now=None) -> None:
        self._repositories = repositories
        self._now = now or (lambda: datetime.now(UTC))

    def approvals(self) -> tuple[FactoryTrainingApproval, ...]:
        return self._repositories.training_approvals.approvals()

    def issue(
        self, *, request_id: str, proposal_id: str, sealed_dataset_id: str,
        approved_dataset_license_ids: tuple[str, ...],
        approved_dataset_sensitivities: tuple[str, ...],
        base_model: ApprovedBaseModel, recipe: AdapterTrainingRecipe,
        resources: TrainingResourceBudget, environment_sha256: str,
        maximum_wall_seconds: int, maximum_checkpoint_bytes: int,
        maximum_output_bytes: int, one_use_job_id: str,
        lifetime_seconds: int, confirmed: bool,
    ) -> FactoryTrainingApproval:
        if not confirmed:
            raise PermissionError("training approval requires confirmation")
        if not 60 <= lifetime_seconds <= 24 * 60 * 60:
            raise ValueError("training approval lifetime must be 60 seconds to 24 hours")
        proposal = next(
            (
                item for item in self._repositories.factory_discovery.proposals()
                if item.proposal_id == proposal_id
            ),
            None,
        )
        if proposal is None:
            raise KeyError("training capability proposal is unavailable")
        dataset = self._repositories.sealed_datasets.get(sealed_dataset_id)
        if dataset is None or not dataset.training_ready or not dataset.immutable:
            raise PermissionError("training requires an immutable training-ready dataset")
        if dataset.proposal_id != proposal.proposal_id:
            raise ValueError("training dataset does not bind the selected proposal")
        if dataset.capability_id != proposal.capability_id:
            raise ValueError("training dataset capability does not match its proposal")
        blobs = self._repositories.sealed_datasets.blobs(dataset.dataset_id)
        if tuple(
            (item.blob_id, item.partition, item.plaintext_sha256) for item in blobs
        ) != tuple(
            (
                item.blob_id, item.partition, item.ordered_records_sha256,
            )
            for item in dataset.partitions
        ):
            raise PermissionError("training dataset partition blobs are incomplete")
        if approved_dataset_license_ids != dataset.license_ids:
            raise PermissionError("all sealed dataset licenses require exact approval")
        if approved_dataset_sensitivities != dataset.sensitivities:
            raise PermissionError("all sealed dataset sensitivities require exact approval")
        now = self._now()
        approval = FactoryTrainingApproval(
            f"training-approval-{request_id}", proposal.proposal_id,
            proposal.capability_id, dataset.dataset_id, dataset.manifest_sha256,
            approved_dataset_license_ids, approved_dataset_sensitivities,
            base_model, recipe, resources, environment_sha256,
            maximum_wall_seconds, maximum_checkpoint_bytes,
            maximum_output_bytes, one_use_job_id, now,
            now + timedelta(seconds=lifetime_seconds), True,
        )
        if not self._repositories.training_approvals.add(approval):
            existing = self._repositories.training_approvals.get(approval.approval_id)
            if existing != approval:
                raise RuntimeError("training approval request identity was reused")
            return existing
        return approval

    def revoke(
        self, *, approval_id: str, expected_revision: int, reason_code: str,
        confirmed: bool,
    ):
        if not confirmed:
            raise PermissionError("training approval revocation requires confirmation")
        return self._repositories.training_approvals.revoke(
            approval_id, expected_revision, reason_code, self._now(),
        )
