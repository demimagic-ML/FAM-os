"""Representative local and remote Git delivery documents."""

from datetime import timedelta

from fam_os.core.engineering import (
    EngineeringAuthority,
    EngineeringAuthorityGrant,
    EngineeringGrantScope,
    EngineeringGrantScopeKind,
    EngineeringResourceImpact,
    GitLocalAction,
    GitLocalActionKind,
    GitLocalActionReceipt,
    GitPublicationApproval,
    GitPublicationKind,
    GitPublicationLocalState,
    GitPublicationProposal,
    GitPublicationReceipt,
    GitRemoteRefObservation,
    GitRemoteRefObservationRequest,
    GitRepositoryObservation,
    LocalGitDeliveryRecord,
    LocalGitDeliveryStatus,
    GrantLifecycleState,
    ReversibilityPolicy,
    SecretExposurePolicy,
    VerificationRequirement,
)
from fam_os.core.engineering.delegation import EngineeringDelegationMode
from tests.contract.schema_engineering_fixtures import NOW


OID = "1" * 40
NEW_OID = "2" * 40


def git_schema_values() -> tuple[object, ...]:
    observation = GitRepositoryObservation(
        "git-observation-1", "task-1", "/workspace", "main", OID,
        (" M src/main.py",), ("refs/heads/main",), ("origin",),
        (OID,), "a" * 64, NOW,
    )
    action = GitLocalAction(
        "git-action-1", "task-1", "/workspace", GitLocalActionKind.COMMIT,
        None, (), "Implement approved change", "change-set-1",
        ("verification-1",), OID, NOW,
    )
    receipt = GitLocalActionReceipt(
        "git-local-receipt-1", action.action_id, OID, NEW_OID, (),
        "b" * 64, NOW,
    )
    stage_action = GitLocalAction(
        "git-stage-1", "task-1", "/workspace",
        GitLocalActionKind.STAGE_PATHS, None, ("src/main.py",), None,
        "change-set-1", ("verification-1",), OID, NOW,
    )
    stage_receipt = GitLocalActionReceipt(
        "git-stage-receipt-1", stage_action.action_id, OID, OID,
        ("src/main.py",), "f" * 64, NOW,
    )
    delivery = LocalGitDeliveryRecord(
        "git-delivery-1", "task-1", "change-set-1", stage_action,
        action, LocalGitDeliveryStatus.COMMITTED,
        ("authorization-1",), 2, NOW, NOW, stage_receipt, receipt,
    )
    approval = GitPublicationApproval(
        "git-publication-1", "task-1", "grant-engineering-1",
        GitPublicationKind.DRAFT_CHANGE_REQUEST, "/workspace", "origin",
        "c" * 64, "refs/heads/feature/engineering",
        "refs/heads/feature/engineering", None, NEW_OID, (NEW_OID,),
        "d" * 64, ("verification-1",), "Implement approved change",
        "Verified candidate change", "secret.git.origin",
        ("Publish one new branch and open one draft PR",),
        NOW, NOW + timedelta(minutes=5),
    )
    publication = GitPublicationReceipt(
        "git-publication-receipt-1", approval.approval_id, "provider-1",
        approval.remote_name, approval.target_ref, None, NEW_OID,
        "https://git.example/change/1", True, NOW, "e" * 64,
    )
    local = GitPublicationLocalState(
        "task-1", "/workspace", "origin", "c" * 64,
        "refs/heads/feature/engineering", NEW_OID, (NEW_OID,), "d" * 64,
        NOW,
    )
    remote_request = GitRemoteRefObservationRequest(
        "git-remote-request-1", "task-1", "/workspace", "origin", "c" * 64,
        "refs/heads/feature/engineering", NEW_OID, "secret.git.origin", NOW,
    )
    remote_observation = GitRemoteRefObservation(
        "git-remote-observation-1", remote_request.request_id, "provider-1",
        "origin", "c" * 64, "refs/heads/feature/engineering", None, NOW,
        "e" * 64,
    )
    proposal_grant = EngineeringAuthorityGrant(
        "publication-grant-1", "owner-1", "owner-1",
        EngineeringDelegationMode.CUSTOM,
        (EngineeringAuthority.PUBLISH, EngineeringAuthority.SECRET_USE),
        EngineeringGrantScope(
            EngineeringGrantScopeKind.TASK, "task-1", ("/workspace",), (),
            (".git/**",), (), (), (), ("origin",),
            ("refs/heads/feature/engineering",), ("secret.git.origin",),
        ),
        "Publish exact verified commit", NOW, NOW + timedelta(minutes=5),
        GrantLifecycleState.ACTIVE, ReversibilityPolicy.BEST_EFFORT,
        SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION,
        VerificationRequirement.REQUIRED,
        EngineeringResourceImpact(120, 3, 1, 0, 0, 8 * 1024 * 1024),
    )
    proposal = GitPublicationProposal(
        "git-publication-proposal-1", "task-1", proposal_grant,
        GitPublicationKind.DRAFT_CHANGE_REQUEST, "/workspace", "origin",
        "c" * 64, "refs/heads/feature/engineering",
        "refs/heads/feature/engineering", None, NEW_OID, (NEW_OID,),
        "d" * 64, ("verification-1",), "Implement approved change",
        "Verified candidate change", "secret.git.origin",
        ("Push one new branch",), remote_observation.observation_id, NOW,
        NOW + timedelta(minutes=5),
    )
    return (
        observation, action, receipt, approval, publication, delivery, local,
        remote_request, remote_observation, proposal,
    )
