"""Owner-scoped Git publication proposal and execution facade."""

from datetime import datetime, timezone

from fam_os.core.engineering import (
    EngineeringAuthority, EngineeringEvidence, EngineeringGrantScopeKind,
    EngineeringLoopStage, EngineeringOutcome,
)


class ProductGitPublicationApi:
    def __init__(
        self, owner_id, grants, task_store, candidates, git_delivery,
        service, lifecycle,
    ) -> None:
        self._owner_id = owner_id
        self._grants = grants
        self._tasks = task_store
        self._candidates = candidates
        self._git_delivery = git_delivery
        self._service = service
        self._lifecycle = lifecycle

    def close(self) -> None:
        if self._service is not None:
            self._service.close()

    def publish_approval(self, owner_id, approval):
        """Execute an owner-supplied exact approval through the same gate."""
        self._require_owner(owner_id)
        self._require_composed()
        state = self._tasks.load(approval.task_id)
        definition = self._tasks.load_task(approval.task_id)
        grant = self._grants.usable(approval.grant_id)
        if state is None or definition is None or grant is None:
            raise KeyError("Git publication inputs are unavailable")
        self.validate_approval(approval)
        if state.stage is EngineeringLoopStage.COMMITTED:
            self._lifecycle.request_publication(approval)
            state = self._tasks.load(approval.task_id)
        if (
            state.stage is not EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED
            or state.pending_publication_id != approval.approval_id
        ):
            raise PermissionError("Git publication is not the pending exact approval")
        receipt = self._service.publish(
            approval, grant, instant=datetime.now(timezone.utc),
        )
        self._lifecycle.record_publication(approval.task_id, receipt)
        return receipt

    def prepare(
        self, owner_id, task_id, changeset_id, *, remote_name, credential_ref,
        title, body,
    ):
        self._require_owner(owner_id)
        self._require_composed(local=True)
        existing = self._service.proposal_for_task(task_id)
        if existing is not None:
            return existing
        definition, state = self._inputs(task_id)
        if state.stage is not EngineeringLoopStage.COMMITTED:
            raise PermissionError("Git publication proposal requires committed state")
        changesets = tuple(
            item for item in self._candidates.changesets(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if len(changesets) != 1:
            raise KeyError("Git publication changeset is unavailable")
        local = self._git_delivery.publication_state(
            definition, changeset_id, remote_name,
        )
        return self._service.prepare(
            local, owner_id=owner_id, target_ref=local.source_ref,
            credential_ref=credential_ref,
            verification_evidence_ids=state.verification_receipt_ids,
            title=title, body=body,
        )

    def for_task(self, owner_id, task_id):
        self._require_owner(owner_id)
        return None if self._service is None else self._service.proposal_for_task(task_id)

    def status(self, owner_id, proposal_id):
        self._require_owner(owner_id)
        return None if self._service is None else self._service.proposal_status(proposal_id)

    def receipt(self, owner_id, proposal_id):
        self._require_owner(owner_id)
        return None if self._service is None else self._service.proposal_receipt(proposal_id)

    def decline(self, owner_id, proposal_id):
        self._require_owner(owner_id)
        self._require_composed()
        return self._service.decline(proposal_id)

    def grant_matches(self, owner_id, grant) -> bool:
        self._require_owner(owner_id)
        return self._grants.usable(grant.grant_id) == grant

    def approve(self, owner_id, proposal_id):
        self._require_owner(owner_id)
        self._require_composed()
        existing = self._service.proposal_receipt(proposal_id)
        if existing is not None:
            return existing
        proposal = self._service.proposal(proposal_id)
        state = self._tasks.load(proposal.task_id)
        grant = self._grants.usable(proposal.grant.grant_id)
        now = datetime.now(timezone.utc)
        if state is None or grant != proposal.grant:
            raise PermissionError("Git publication requires its exact active grant")
        if state.stage is not EngineeringLoopStage.COMMITTED:
            raise PermissionError("Git publication task is no longer committed")
        approval = self._service.begin_approval(proposal_id, instant=now)
        self.validate_approval(approval)
        self._lifecycle.request_publication(approval)
        receipt = self._service.publish_proposal(
            proposal_id, approval, grant, instant=now,
        )
        self._lifecycle.record_publication(proposal.task_id, receipt)
        self._lifecycle.complete(EngineeringEvidence(
            f"engineering-complete-{proposal_id}", proposal.task_id,
            receipt.completed_at, EngineeringOutcome.SUCCEEDED, (),
            (proposal.proposal_id,), (approval.approval_id,), (),
            proposal.verification_evidence_ids,
            (proposal.complete_diff_sha256,), (), (),
        ))
        return receipt

    def validate_approval(self, approval) -> None:
        grant = self._grants.usable(approval.grant_id)
        definition = self._tasks.load_task(approval.task_id)
        if (
            grant is None
            or definition is None
            or grant.owner_id != self._owner_id
            or not grant.active_at(approval.approved_at)
            or EngineeringAuthority.PUBLISH not in grant.authorities
            or grant.scope.kind is not EngineeringGrantScopeKind.TASK
            or grant.scope.scope_id != approval.task_id
            or approval.repository_root not in grant.scope.workspace_roots
            or approval.remote_name not in grant.scope.git_remotes
            or approval.target_ref not in grant.scope.git_branches
            or approval.repository_root not in definition.task.workspace_roots
        ):
            raise PermissionError(
                "Git publication approval lacks its separate exact grant"
            )

    def _inputs(self, task_id):
        definition = self._tasks.load_task(task_id)
        state = self._tasks.load(task_id)
        if definition is None or state is None:
            raise KeyError("Git publication task is unavailable")
        return definition, state

    def _require_composed(self, *, local=False) -> None:
        if self._service is None or (local and self._git_delivery is None):
            raise RuntimeError("Git publication preparation was not composed")

    def _require_owner(self, owner_id) -> None:
        if owner_id != self._owner_id:
            raise PermissionError("engineering task owner is invalid")
