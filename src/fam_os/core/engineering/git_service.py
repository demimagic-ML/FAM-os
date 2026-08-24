"""Fail-closed proposal and publication gate over provider-neutral brokers."""

from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.git_delivery import GitPublicationApproval, GitPublicationKind, GitPublicationReceipt
from fam_os.core.engineering.git_publication_proposal import (
    GitPublicationLocalState, GitPublicationProposal,
    GitRemoteRefObservation, GitRemoteRefObservationRequest,
)
from fam_os.core.engineering.delegation import EngineeringDelegationMode
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant, EngineeringGrantScope,
    EngineeringGrantScopeKind, EngineeringResourceImpact,
    GrantLifecycleState, ReversibilityPolicy, SecretExposurePolicy,
    VerificationRequirement,
)


class GitPublicationProvider(Protocol):
    def observe(
        self, request: GitRemoteRefObservationRequest,
    ) -> GitRemoteRefObservation: ...
    def publish(self, approval: GitPublicationApproval) -> GitPublicationReceipt: ...


class PublicationConsumptionStore(Protocol):
    def consume_once(self, approval_id: str) -> bool: ...


class GitPublicationProposalStore(Protocol):
    def put(self, proposal: GitPublicationProposal) -> None: ...
    def get(self, proposal_id: str) -> GitPublicationProposal | None: ...
    def for_task(self, task_id: str) -> GitPublicationProposal | None: ...
    def status(self, proposal_id: str) -> str | None: ...
    def begin_approval(self, proposal_id: str) -> bool: ...
    def decline(self, proposal_id: str) -> bool: ...
    def mark_published(self, proposal_id: str, receipt: GitPublicationReceipt) -> None: ...
    def mark_recovery_required(self, proposal_id: str) -> None: ...
    def receipt(self, proposal_id: str) -> GitPublicationReceipt | None: ...


class GitPublicationService:
    def __init__(
        self, provider: GitPublicationProvider,
        consumptions: PublicationConsumptionStore,
        proposals: GitPublicationProposalStore | None = None,
        *, clock=None, identifier=None,
    ) -> None:
        self._provider = provider
        self._consumptions = consumptions
        self._proposals = proposals
        self._clock = clock
        self._identifier = identifier or (lambda: uuid4().hex)

    def close(self) -> None:
        for store in (self._proposals, self._consumptions):
            close = getattr(store, "close", None)
            if close is not None:
                close()

    def prepare(
        self, local: GitPublicationLocalState, *, owner_id: str,
        target_ref: str, credential_ref: str,
        verification_evidence_ids: tuple[str, ...], title: str, body: str,
    ) -> GitPublicationProposal:
        """Observe a remote and persist a proposal without mutation authority."""
        if self._proposals is None:
            raise RuntimeError("Git publication proposal storage was not composed")
        if target_ref != local.source_ref or _protected(target_ref):
            raise PermissionError(
                "ordinary publication requires the current non-protected feature ref"
            )
        now = self._clock() if self._clock is not None else local.observed_at
        request = GitRemoteRefObservationRequest(
            f"git-remote-observation-{self._identifier()}", local.task_id,
            local.repository_root, local.remote_name, local.remote_url_sha256,
            target_ref, local.proposed_new_object_id, credential_ref, now,
        )
        observed = self._provider.observe(request)
        if (
            observed.request_id != request.request_id
            or observed.remote_name != request.remote_name
            or observed.remote_url_sha256 != request.remote_url_sha256
            or observed.target_ref != request.target_ref
            or observed.observed_at < request.requested_at
            or observed.observed_at > request.requested_at + timedelta(minutes=1)
        ):
            raise RuntimeError("Git provider observation does not match the request")
        if observed.observed_object_id is not None:
            raise PermissionError(
                "existing remote refs require the advanced reconciliation workflow"
            )
        expires = now + timedelta(minutes=5)
        token = self._identifier()
        grant = _publication_grant(
            f"publication-grant-{token}", owner_id, local, target_ref,
            credential_ref, now, expires,
        )
        proposal = GitPublicationProposal(
            f"git-publication-{token}", local.task_id, grant,
            GitPublicationKind.DRAFT_CHANGE_REQUEST, local.repository_root,
            local.remote_name, local.remote_url_sha256, local.source_ref,
            target_ref, observed.observed_object_id,
            local.proposed_new_object_id, local.commit_object_ids,
            local.complete_diff_sha256, verification_evidence_ids, title, body,
            credential_ref,
            (
                f"Push {target_ref} to {local.remote_name} only if it is absent.",
                "Open one draft change request for the exact verified commits.",
                "Use one opaque broker credential reference; expose no secret value.",
                "Stop on any remote, ref, object, diff, grant, or provider drift.",
            ),
            observed.observation_id, now, expires,
        )
        self._proposals.put(proposal)
        return proposal

    def proposal(self, proposal_id: str) -> GitPublicationProposal:
        if self._proposals is None:
            raise RuntimeError("Git publication proposal storage was not composed")
        value = self._proposals.get(proposal_id)
        if value is None:
            raise KeyError("Git publication proposal is unavailable")
        return value

    def proposal_status(self, proposal_id: str) -> str | None:
        return None if self._proposals is None else self._proposals.status(proposal_id)

    def proposal_for_task(self, task_id: str) -> GitPublicationProposal | None:
        return None if self._proposals is None else self._proposals.for_task(task_id)

    def begin_approval(
        self, proposal_id: str, *, instant: datetime,
    ) -> GitPublicationApproval:
        proposal = self.proposal(proposal_id)
        if not self._proposals.begin_approval(proposal_id):
            raise PermissionError(
                "Git publication proposal confirmation is unavailable or consumed"
            )
        return proposal.approval(instant)

    def decline(self, proposal_id: str) -> GitPublicationProposal:
        proposal = self.proposal(proposal_id)
        if not self._proposals.decline(proposal_id):
            raise PermissionError("Git publication proposal cannot be declined")
        return proposal

    def publish_proposal(
        self, proposal_id: str, approval: GitPublicationApproval,
        grant: EngineeringAuthorityGrant, *, instant: datetime,
    ) -> GitPublicationReceipt:
        proposal = self.proposal(proposal_id)
        if approval != proposal.approval(approval.approved_at):
            raise PermissionError("Git publication approval differs from its proposal")
        try:
            receipt = self.publish(approval, grant, instant=instant)
        except BaseException:
            self._proposals.mark_recovery_required(proposal_id)
            raise
        self._proposals.mark_published(proposal_id, receipt)
        return receipt

    def proposal_receipt(self, proposal_id: str) -> GitPublicationReceipt | None:
        return None if self._proposals is None else self._proposals.receipt(proposal_id)

    def publish(self, approval: GitPublicationApproval, grant: EngineeringAuthorityGrant, *, instant: datetime) -> GitPublicationReceipt:
        if not grant.active_at(instant) or grant.grant_id != approval.grant_id:
            raise PermissionError("Git publication grant is inactive or mismatched")
        if EngineeringAuthority.PUBLISH not in grant.authorities:
            raise PermissionError("Git publication authority was not granted")
        if approval.remote_name not in grant.scope.git_remotes:
            raise PermissionError("Git remote is outside the grant")
        exceptional = {
            GitPublicationKind.FORCE_PUSH,
            GitPublicationKind.PROTECTED_REF_WRITE,
            GitPublicationKind.TAG_REF_CHANGE,
            GitPublicationKind.REMOTE_CHANGE,
        }
        if approval.kind in exceptional and EngineeringAuthority.PROTECTED_REF_WRITE not in grant.authorities:
            raise PermissionError("exceptional ref mutation requires its exact authority")
        if not approval.approved_at <= instant < approval.expires_at:
            raise PermissionError("Git publication approval is expired")
        if not self._consumptions.consume_once(approval.approval_id):
            raise PermissionError("Git publication approval was already consumed")
        receipt = self._provider.publish(approval)
        if receipt.approval_id != approval.approval_id or receipt.published_new_object_id != approval.proposed_new_object_id:
            raise ValueError("Git provider receipt does not match the approved publication")
        return receipt


def _publication_grant(
    grant_id, owner_id, local, target_ref, credential_ref, issued_at, expires_at,
):
    return EngineeringAuthorityGrant(
        grant_id, owner_id, owner_id, EngineeringDelegationMode.CUSTOM,
        (EngineeringAuthority.PUBLISH, EngineeringAuthority.SECRET_USE),
        EngineeringGrantScope(
            EngineeringGrantScopeKind.TASK, local.task_id,
            (local.repository_root,), (), (".git/**",), (), (), (),
            (local.remote_name,), (target_ref,), (credential_ref,),
        ),
        "Publish the exact verified FAM commit through the credential-opaque broker",
        issued_at, expires_at, GrantLifecycleState.ACTIVE,
        ReversibilityPolicy.BEST_EFFORT,
        SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION,
        VerificationRequirement.REQUIRED,
        EngineeringResourceImpact(120, 3, 1, 0, 0, 8 * 1024 * 1024),
    )


def _protected(ref: str) -> bool:
    return ref in {
        "refs/heads/main", "refs/heads/master", "refs/heads/trunk",
        "refs/heads/production", "refs/heads/prod",
    }
