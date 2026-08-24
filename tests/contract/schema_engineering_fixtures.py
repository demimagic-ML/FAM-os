"""Representative owner-delegated engineering schema values."""

from datetime import datetime, timedelta, timezone

from fam_os.core.engineering import (
    ChangeSetProposal,
    BreakGlassChallenge,
    BreakGlassDecision,
    BreakGlassDisposition,
    CheckpointDecision,
    CheckpointDisposition,
    CheckpointPolicy,
    DependencyAction,
    DependencyChange,
    DependencyPlan,
    DesignAsset,
    DesignAssetManifest,
    EngineeringAuthority,
    EngineeringAuthorityGrant,
    EngineeringAuthorizationDecision,
    EngineeringAuthorizationRequest,
    EngineeringCapabilityUnavailable,
    EngineeringEvidence,
    EngineeringDelegationMode,
    EngineeringExecutionAssurance,
    EngineeringExecutionRecord,
    EngineeringGrantScope,
    EngineeringGrantScopeKind,
    EngineeringOperation,
    EngineeringOutcome,
    EngineeringProposalResult,
    EngineeringPublicationProposal,
    EngineeringPublicationReceipt,
    EngineeringTaskEnvelope,
    EngineeringResourceImpact,
    FileOperation,
    FileOperationKind,
    GitOperation,
    GitOperationKind,
    ToolRecipe,
    ToolRun,
    ToolRunStatus,
    GrantLifecycleState,
    OwnerGrantApproval,
    ReversibilityPolicy,
    SecretExposurePolicy,
    VerificationRequirement,
    VerifiedChangeSetReceipt,
    WorkspaceEntry,
    WorkspaceSnapshot,
    consequences_digest,
    expand_delegation,
)
from fam_os.core.engineering.grant_policy import engineering_grant_digest


NOW = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def engineering_schema_values() -> tuple[object, ...]:
    task = EngineeringTaskEnvelope(
        "task-1", "owner-1", "grant-1", "Implement and verify a bounded change",
        NOW, NOW + timedelta(hours=1), ("/workspace",),
        (
            EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
            EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE,
            EngineeringAuthority.NETWORK, EngineeringAuthority.PUBLISH,
        ),
        (
            EngineeringOperation.READ, EngineeringOperation.CREATE,
            EngineeringOperation.RUN_TOOL, EngineeringOperation.MANAGE_DEPENDENCY,
            EngineeringOperation.GIT_WRITE,
        ),
        ("src/**", "tests/**"), (".git/**",), ("python3",),
        ("pypi.org",), ("https://pypi.org/simple",), 3600, 20, 12, 100_000,
        "origin", "feature/engineering", CheckpointPolicy.EVERY_CHANGESET,
    )
    entry = WorkspaceEntry("src/example.py", DIGEST_A, 10, False)
    snapshot = WorkspaceSnapshot(
        "snapshot-1", task.task_id, NOW, "/workspace", "abc123", (entry,), DIGEST_B,
    )
    operation = FileOperation(
        "operation-1", FileOperationKind.REPLACE, entry.path, DIGEST_A, DIGEST_B,
        None, True,
    )
    proposal = ChangeSetProposal(
        "proposal-1", task.task_id, snapshot.snapshot_id, NOW, "Apply tested edit",
        (operation,), (EngineeringAuthority.MODIFY,), 10, True,
    )
    recipe = ToolRecipe(
        "recipe-1", task.task_id, ("python3", "-m", "unittest"), "/workspace",
        ("PYTHONPATH",), 120, False, (EngineeringAuthority.EXECUTE,), (0,),
        ("python-tests",),
    )
    run = ToolRun(
        "run-1", task.task_id, recipe.recipe_id, NOW, NOW + timedelta(seconds=2),
        ToolRunStatus.SUCCEEDED, 0, DIGEST_A, DIGEST_B, ("test-evidence-1",),
    )
    dependency = DependencyPlan(
        "dependency-plan-1", task.task_id, "requirements.lock",
        (DependencyChange("python", "jsonschema", DependencyAction.UPDATE, "4.0", "4.1", "pypi"),),
        (EngineeringAuthority.MODIFY, EngineeringAuthority.NETWORK), True, True,
    )
    design = DesignAssetManifest(
        "design-1", task.task_id, NOW, "fam-design-v1",
        (DesignAsset("assets/icon.png", "image/png", DIGEST_A, None, 64, 64),),
        ("image-dimensions", "accessibility"), True,
    )
    git = GitOperation(
        "git-1", task.task_id, GitOperationKind.PUSH, "/workspace", "origin",
        "feature/engineering", "feature/engineering", DIGEST_A, "Publish verified change",
        (EngineeringAuthority.MODIFY, EngineeringAuthority.PUBLISH), False,
    )
    checkpoint = CheckpointDecision(
        "decision-1", task.task_id, proposal.proposal_id, "checkpoint-1", "owner-1",
        NOW, CheckpointDisposition.APPROVED, DIGEST_A, "Approved bounded proposal",
    )
    evidence = EngineeringEvidence(
        "engineering-evidence-1", task.task_id, NOW, EngineeringOutcome.SUCCEEDED,
        (snapshot.snapshot_id,), (proposal.proposal_id,), (checkpoint.decision_id,),
        (run.run_id,), ("python-tests",), (DIGEST_A,), (entry.path,), (),
    )
    return (
        task, snapshot, operation, proposal, recipe, run, dependency, design, git,
        checkpoint, evidence,
    )


def engineering_result_schema_values() -> tuple[object, ...]:
    (
        task, before, operation, proposal, _recipe, run, _dependency, _design,
        _git, checkpoint, _evidence,
    ) = engineering_schema_values()
    after = WorkspaceSnapshot(
        "snapshot-2", task.task_id, NOW + timedelta(seconds=3), "/workspace",
        "def456", (WorkspaceEntry("src/example.py", DIGEST_B, 12, False),), DIGEST_A,
    )
    proposal_result = EngineeringProposalResult(
        "result-proposal-1", task.task_id, proposal.proposal_id, NOW,
        "Ready for owner checkpoint", ("checkpoint-1",),
    )
    change_receipt = VerifiedChangeSetReceipt(
        "receipt-change-1", task.task_id, proposal.proposal_id,
        before.snapshot_id, after.snapshot_id, NOW + timedelta(seconds=4),
        (operation.operation_id,), (run.run_id,), ("verifier-run-1",),
        ("evidence-1",), (operation.path,), before.tree_sha256, after.tree_sha256,
    )
    publication_proposal = EngineeringPublicationProposal(
        "publication-1", task.task_id, NOW + timedelta(seconds=5), "git_push",
        "origin", "feature/engineering", "main", (DIGEST_A,),
        "Publish the verified changeset", "publication-checkpoint-1",
        (EngineeringAuthority.PUBLISH,),
    )
    publication_receipt = EngineeringPublicationReceipt(
        "publication-receipt-1", task.task_id, publication_proposal.proposal_id,
        "publication-decision-1", NOW + timedelta(seconds=6),
        "https://example.invalid/change/1", "remote-revision-1",
        ("publication-evidence-1",), ("publication-postcondition-1",),
    )
    unavailable = EngineeringCapabilityUnavailable(
        "unavailable-1", task.task_id, NOW, "engineering.host_admin",
        (EngineeringAuthority.HOST_ADMIN,), "grant_required",
        "The owner has not granted host administration for this task.", True,
    )
    return (
        proposal_result, change_receipt, publication_proposal,
        publication_receipt, unavailable,
    )


def engineering_grant_schema_values() -> tuple[object, ...]:
    authorities = expand_delegation(EngineeringDelegationMode.FULL_OWNER)
    scope = EngineeringGrantScope(
        EngineeringGrantScopeKind.TASK, "task-1", ("/workspace",),
        ("src/**",), (".git/**",), ("python3",), ("pypi.org",),
        ("https://pypi.org/simple",), ("origin",), ("feature/engineering",),
        ("secret.api",),
    )
    impact = EngineeringResourceImpact(3600, 20, 8, 20, 1_000_000, 10_000_000)
    consequences = (
        "Commands may run with administrator authority.",
        "Verification is explicitly waived for this bounded task.",
    )
    challenge = BreakGlassChallenge(
        "break-glass-1", "owner-1", "grant-engineering-1", authorities,
        VerificationRequirement.WAIVED, scope.kind, scope.scope_id, consequences,
        consequences_digest(consequences), NOW, NOW + timedelta(minutes=10),
    )
    decision = BreakGlassDecision(
        "break-glass-decision-1", challenge.challenge_id, challenge.owner_id,
        challenge.grant_id, BreakGlassDisposition.APPROVED, challenge.scope_kind,
        challenge.scope_id, challenge.consequences_sha256, NOW + timedelta(minutes=1),
        "owner-authenticated",
    )
    grant = EngineeringAuthorityGrant(
        challenge.grant_id, challenge.owner_id, "fam-core", EngineeringDelegationMode.FULL_OWNER,
        authorities, scope, "Complete the owner-approved task", NOW,
        NOW + timedelta(hours=1), GrantLifecycleState.ACTIVE,
        ReversibilityPolicy.BEST_EFFORT,
        SecretExposurePolicy.PLAINTEXT_TO_APPROVED_TOOL,
        VerificationRequirement.WAIVED, impact, False, decision.decision_id,
    )
    approval = OwnerGrantApproval(
        "grant-approval-1", grant.grant_id, grant.owner_id,
        engineering_grant_digest(grant), NOW + timedelta(minutes=2),
        "owner-authenticated",
    )
    request = EngineeringAuthorizationRequest(
        "authorization-request-1", grant.grant_id, grant.principal_id,
        EngineeringAuthority.MODIFY, "task-1", "session-1", None, None,
        "/workspace", "src/example.py", "python3", "pypi.org",
        "https://pypi.org/simple", "origin", "feature/engineering",
        "secret.api", EngineeringResourceImpact(60, 1, 1, 1, 1000, 1000),
    )
    authorization = EngineeringAuthorizationDecision(
        "authorization-1", request.request_id, grant.grant_id, request.authority,
        NOW + timedelta(minutes=3), True, "authorized",
    )
    execution = EngineeringExecutionRecord(
        "execution-1", "task-1", grant.grant_id, "effect-1",
        NOW + timedelta(minutes=4), True, EngineeringExecutionAssurance.VERIFIED,
        ("verifier-run-1",), ("effect-evidence-1",),
    )
    return grant, approval, request, authorization, challenge, decision, execution
