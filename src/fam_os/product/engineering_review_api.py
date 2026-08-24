"""Owner-scoped policy, attachment, evidence, and passage for reviews."""

from fam_os.core.engineering import (
    EngineeringReviewSelection,
    EngineeringReviewSelectionPolicy,
    candidate_preview_digest,
)


class ProductEngineeringReviewApi:
    def __init__(
        self, owner_id, task_store, preparations, candidates, service=None,
    ) -> None:
        self._owner_id = owner_id
        self._tasks = task_store
        self._preparations = preparations
        self._candidates = candidates
        self._service = service
        self._policy = EngineeringReviewSelectionPolicy()

    def record_selection(self, owner_id, selection):
        """Persist the one deterministic policy result for an exact changeset."""
        self._require_owner(owner_id)
        self._require_composed()
        task, changeset = self._exact_inputs(
            owner_id, selection.task_id, selection.candidate_id,
            selection.changeset_sha256,
        )
        expected = self._policy.select(task, changeset)
        if selection != expected:
            raise PermissionError("engineering review selection differs from policy")
        self._service.record_selection(selection)
        return selection

    def record_trusted(self, owner_id, checkpoint):
        """Attach output from a separately trusted reviewer adapter."""
        self._require_owner(owner_id)
        self._require_composed()
        self._exact_inputs(
            owner_id, checkpoint.task_id, checkpoint.candidate_id,
            checkpoint.changeset_sha256,
        )
        self._service.record(checkpoint)
        return checkpoint

    def record_trusted_resolution(self, owner_id, receipt):
        """Resolve only from typed evidence already held by Core."""
        self._require_owner(owner_id)
        self._require_composed()
        self._exact_inputs(
            owner_id, receipt.task_id, receipt.candidate_id,
            receipt.changeset_sha256,
        )
        verifications = tuple(
            item for item in self._candidates.verifications(
                owner_id, receipt.task_id,
            )
            if item.passed and item.evidence is not None
        )
        trusted_verification = {
            item.evidence.evidence_id for item in verifications
        }
        edits = self._candidates.edits(owner_id, receipt.task_id)
        trusted_remediation = {
            value
            for item in edits
            for value in (item.edit_id, item.operation.operation_id)
        }
        if (
            not set(receipt.verification_evidence_ids).issubset(
                trusted_verification
            )
            or not set(receipt.remediation_evidence_ids).issubset(
                trusted_remediation | trusted_verification
            )
        ):
            raise PermissionError("review resolution cites untrusted remediation evidence")
        return self._service.resolve(receipt)

    def waive(self, owner_id, decision):
        self._require_owner(owner_id)
        self._require_composed()
        if decision.owner_id != owner_id:
            raise PermissionError("engineering review waiver owner is invalid")
        return self._service.waive(decision)

    def for_task(self, owner_id, task_id):
        self._require_owner(owner_id)
        if self._service is None:
            return ()
        return self._service.for_task(task_id)

    def evidence_for_task(self, owner_id, task_id):
        self._require_owner(owner_id)
        if self._service is None:
            return ()
        return self._service.evidence_for_task(task_id)

    def require_passage(self, owner_id, task_id, changeset):
        self._require_owner(owner_id)
        if self._service is None:
            return ()
        digest = candidate_preview_digest(changeset.preview)
        selections = tuple(
            item for item in self._service.evidence_for_task(task_id)
            if isinstance(item, EngineeringReviewSelection)
            and item.changeset_sha256 == digest
        )
        checkpoints = tuple(
            item for item in self._service.for_task(task_id)
            if item.changeset_sha256 == digest
        )
        if len(selections) != 1 or not checkpoints:
            raise PermissionError(
                "policy-selected independent engineering review is missing"
            )
        if any(
            checkpoint.required_disciplines
            != selections[0].required_disciplines
            for checkpoint in checkpoints
        ):
            raise PermissionError("engineering review disciplines differ from policy")
        for checkpoint in checkpoints:
            self._service.require_passage(checkpoint.checkpoint_id)
        return checkpoints

    def close(self):
        if self._service is not None:
            self._service.close()

    def _require_owner(self, owner_id):
        if owner_id != self._owner_id:
            raise PermissionError("engineering review owner is invalid")

    def _require_composed(self):
        if self._service is None:
            raise RuntimeError("engineering review service was not composed")

    def _exact_inputs(self, owner_id, task_id, candidate_id, preview_sha256):
        loader = getattr(self._tasks, "load_task", self._tasks.load)
        task = loader(task_id)
        preparation = self._preparations.load(task_id)
        changesets = tuple(
            item for item in self._candidates.changesets(owner_id, task_id)
            if candidate_preview_digest(item.preview) == preview_sha256
        )
        if (
            task is None or preparation is None or len(changesets) != 1
            or candidate_id != preparation.candidate.candidate_id
        ):
            raise PermissionError(
                "engineering review is not bound to the exact task candidate changeset"
            )
        return task, changesets[0]
