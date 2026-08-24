import base64
import hashlib
from dataclasses import replace
from datetime import datetime, timezone

from fam_os.core.contracts import ResultStatus
from fam_os.shell import (
    ShellApprovalRequest,
    ShellAskCommand,
    ShellCancelCommand,
    ShellContext,
    ShellContextKind,
    ShellDecision,
    ShellDecisionCommand,
    ShellPlanStep,
    ShellRunState,
    ShellSessionSnapshot,
    ShellSessionSnapshotV1Alpha1,
    ShellResultV1Alpha1,
    ShellSnapshotQuery,
    ShellStepState,
    ShellVerifiedAskCommand,
    ShellMemoryOperation,
    ShellMemoryQuery,
    ShellMemoryResponse,
    ShellAdaptationOperation,
    ShellAdaptationQuery,
    ShellAdaptationResponse,
    ShellPeerOperation,
    ShellPeerProbeRequest,
    ShellPeerQuery,
    ShellPeerResponse,
    ShellEngineeringActivationRequest,
    ShellEngineeringAuthorityOperation,
    ShellEngineeringAuthorityResponse,
    ShellEngineeringContextRequest,
    ShellEngineeringGrantQuery,
    ShellEngineeringRevocationRequest,
    ShellIntegrationEnvironmentControlRequest,
    ShellIntegrationEnvironmentOperation,
    ShellIntegrationEnvironmentQuery,
    ShellIntegrationEnvironmentRecord,
    ShellIntegrationEnvironmentResponse,
    ShellIntegrationEnvironmentStartRequest,
    ShellEngineeringSecretAuditEvent,
    ShellEngineeringSecretMetadata,
    ShellEngineeringSecretMutation,
    ShellEngineeringSecretOperation,
    ShellEngineeringSecretQuery,
    ShellEngineeringSecretResponse,
    ShellEngineeringLoopMutation,
    ShellEngineeringLoopOperation,
    ShellEngineeringLoopQuery,
    ShellEngineeringLoopResponse,
    ShellEngineeringLoopStartRequest,
    ShellEngineeringLoopView,
    ShellEngineeringCandidateEditRequest,
    ShellEngineeringCandidateVerificationRequest,
    ShellEngineeringCandidateReverificationRequest,
    ShellEngineeringChangesetApplyRequest,
    ShellEngineeringChangesetPreviewRequest,
    ShellEngineeringIncidentAdvanceRequest,
    ShellEngineeringPublicationRequest,
)
from fam_os.verification import ExactTextVerification, VerificationDeclaration, contract_for_kind
from fam_os.schemas import dumps_document
from fam_os.fabric import RemoteContextSensitivity, RemoteExecutionAuthority
from tests.contract.schema_manifest_fixtures import (
    document_management_values,
    live_adaptation_control_values,
    device_identity_values,
)
from tests.contract.schema_engineering_fixtures import (
    NOW, engineering_grant_schema_values, engineering_schema_values,
)
from tests.contract.schema_diagnostics_fixtures import diagnostics_schema_values
from tests.contract.schema_database_engineering_fixtures import (
    database_engineering_schema_values, database_postapply_schema_values,
)
from tests.contract.schema_integration_environment_fixtures import (
    integration_environment_schema_values,
)
from fam_os.core.engineering import (
    CandidateArtifact, CandidateContentKind, CandidateOperation,
    CandidateOperationKind, CandidateWorkspace, EngineeringLoopBudget,
    EngineeringTaskDefinition,
    EngineeringIncidentStage, engineering_task_digest,
)
from tests.contract.schema_candidate_changeset_fixtures import candidate_changeset_schema_values
from tests.contract.schema_git_fixtures import git_schema_values
from tests.contract.schema_review_fixtures import review_schema_values
from tests.contract.schema_documentation_fixtures import documentation_schema_values


def shell_schema_values() -> tuple[object, ...]:
    edit_content = b"generated = 1\n"
    edit_artifact = CandidateArtifact(
        "artifact-shell-schema-1", CandidateContentKind.TEXT, "text/x-python",
        hashlib.sha256(edit_content).hexdigest(), len(edit_content), "owner-request",
    )
    changeset = candidate_changeset_schema_values()[0]
    publication_approval = git_schema_values()[3]
    review_values = review_schema_values()
    review = review_values[0]
    documentation = documentation_schema_values()
    diagnostic_request, diagnostic_receipt = diagnostics_schema_values()
    _target, database_plan, _permit, database_backup, database_receipt = (
        database_engineering_schema_values()
    )
    database_postapply = database_postapply_schema_values()[0]
    context = ShellContext(
        "context-1", ShellContextKind.APPLICATION, "app:editor", "Editor",
        ("editor.observe",),
    )
    approval = ShellApprovalRequest(
        "approval-1", "proposal-1", "editor.write", "Apply edit",
        datetime(2026, 7, 18, tzinfo=timezone.utc), True,
    )
    snapshot = ShellSessionSnapshot(
        "session-1", "request-1", 1, ShellRunState.WAITING_APPROVAL,
        steps=(ShellPlanStep(
            "edit", "execute_action", "Apply edit", ShellStepState.ACTIVE,
        ),),
        current_step_id="edit", message="Prepared", approval=approval,
    )
    verified_specification = ExactTextVerification("READY")
    verified_declaration = VerificationDeclaration(
        "declaration-request-2", "request-2",
        contract_for_kind(verified_specification.kind), verified_specification,
    )
    management = document_management_values()
    management_receipt = management[4]
    adaptation_state = live_adaptation_control_values()[0]
    peer_entry = device_identity_values()[-1]
    engineering = engineering_grant_schema_values()
    grant, grant_approval = engineering[0], engineering[1]
    base_task = engineering_schema_values()[0]
    loop_task = replace(
        base_task, grant_id=grant.grant_id, owner_id=grant.owner_id,
        authorities=grant.authorities,
    )
    loop_definition = EngineeringTaskDefinition(
        f"definition-{loop_task.task_id}", loop_task, "acceptance-1", NOW,
        engineering_task_digest(loop_task),
    )
    challenge, break_glass = engineering[4], engineering[5]
    _service, integration_plan, _permit, integration_receipt, integration_result = (
        integration_environment_schema_values()
    )
    integration_candidate = CandidateWorkspace(
        integration_plan.candidate_id, integration_plan.task_id, "baseline-1",
        "/owner/workspace", integration_plan.candidate_root,
        integration_plan.created_at, "copy", "a" * 64, (),
    )
    integration_record = ShellIntegrationEnvironmentRecord(
        "active", integration_plan, integration_candidate,
        integration_result, integration_receipt,
    )
    return (
        ShellAskCommand(
            "request-1", "Review this", (context,), ("editor.observe",), True,
        ),
        ShellAskCommand(
            "remote-request", "Explain this remotely",
            remote_authority=RemoteExecutionAuthority(
                "enrollment", 1, "assist", "workspace:test",
                RemoteContextSensitivity.PRIVATE, 4096, 4096, True,
            ),
        ),
        ShellVerifiedAskCommand(
            ShellAskCommand("request-2", "Return READY", verification_required=True),
            dumps_document(verified_declaration),
        ),
        ShellSnapshotQuery("session-1"),
        ShellDecisionCommand(
            "session-1", 1, "approval-1", ShellDecision.APPROVE,
        ),
        ShellCancelCommand("session-1", 1),
        snapshot,
        ShellSessionSnapshotV1Alpha1(
            "legacy-session", "legacy-request", 1, ShellRunState.TERMINAL,
            result=ShellResultV1Alpha1(
                "legacy-request", ResultStatus.COMPLETED, "legacy answer",
            ),
        ),
        ShellMemoryQuery("memory-list-1", ShellMemoryOperation.LIST),
        ShellMemoryResponse(
            management_receipt.request_id, ShellMemoryOperation.CORRECT,
            total_count=1, receipt=management_receipt,
        ),
        ShellAdaptationQuery(
            "adaptation-status-1", ShellAdaptationOperation.STATUS, limit=1,
        ),
        ShellAdaptationResponse(
            "adaptation-status-1", ShellAdaptationOperation.STATUS,
            0, 1, state=adaptation_state,
        ),
        ShellPeerQuery("peer-list-1", ShellPeerOperation.PEERS),
        ShellPeerProbeRequest("peer-probe-1", peer_entry.enrollment_id),
        ShellPeerResponse(
            "peer-list-1", ShellPeerOperation.PEERS, 0, 1, peers=(peer_entry,),
        ),
        ShellEngineeringSecretQuery(
            "secret-list-1", ShellEngineeringSecretOperation.LIST,
        ),
        ShellEngineeringSecretMutation(
            "secret-provision-1", ShellEngineeringSecretOperation.PROVISION,
            "authority-session-1", grant.owner_id, "context-1", "secret.api",
            "API_TOKEN", "integration:api", "protected", True,
        ),
        ShellEngineeringSecretResponse(
            "secret-list-1", ShellEngineeringSecretOperation.LIST,
            items=(ShellEngineeringSecretMetadata(
                "secret.api", "API_TOKEN", "integration:api", "active", 1,
                datetime(2026, 7, 19, tzinfo=timezone.utc),
                datetime(2026, 7, 19, tzinfo=timezone.utc),
            ),),
        ),
        ShellIntegrationEnvironmentStartRequest(
            "integration-start-1", "authority-session-1", grant.owner_id,
            integration_plan, integration_candidate, grant.grant_id,
            grant.principal_id, True,
        ),
        ShellIntegrationEnvironmentQuery(
            "integration-query-1", ShellIntegrationEnvironmentOperation.INSPECT,
            grant.owner_id, integration_plan.environment_id,
        ),
        ShellIntegrationEnvironmentControlRequest(
            "integration-cleanup-1", ShellIntegrationEnvironmentOperation.CLEANUP,
            grant.owner_id, integration_plan.environment_id, True,
        ),
        ShellIntegrationEnvironmentResponse(
            "integration-query-1", ShellIntegrationEnvironmentOperation.INSPECT,
            record=integration_record,
        ),
        ShellEngineeringLoopStartRequest(
            "loop-start-1", grant.owner_id, loop_definition,
            EngineeringLoopBudget(1000, 100, 20, 1000, 20, 10_000), True,
        ),
        ShellEngineeringLoopQuery(
            "loop-query-1", ShellEngineeringLoopOperation.INSPECT,
            grant.owner_id, "task-1",
        ),
        ShellEngineeringLoopMutation(
            "loop-resume-1", ShellEngineeringLoopOperation.RESUME,
            grant.owner_id, "task-1",
        ),
        ShellEngineeringLoopResponse(
            "loop-query-1", ShellEngineeringLoopOperation.INSPECT,
            view=ShellEngineeringLoopView(
                "task-1", "Implement task", ("/workspace",), "acceptance-1",
                "requested", 0, None, None, None,
                (), (), (), (), (), (), (), (), (), (), None,
                {"tokens": 0, "wall_seconds": 0, "commands": 0,
                 "network_bytes": 0, "files": 0, "storage_bytes": 0},
            ),
        ),
        ShellEngineeringLoopResponse(
            "loop-reviews-1", ShellEngineeringLoopOperation.REVIEWS,
            reviews=(review,),
            review_evidence=(
                review_values[1], review_values[2], review_values[4],
            ),
        ),
        ShellEngineeringLoopResponse(
            "loop-documentation-1", ShellEngineeringLoopOperation.DOCUMENTATION,
            documentation=documentation,
        ),
        ShellEngineeringLoopQuery(
            "loop-diagnostics-1",
            ShellEngineeringLoopOperation.RUNTIME_DIAGNOSTICS,
            grant.owner_id, "task-1",
        ),
        ShellEngineeringLoopResponse(
            "loop-diagnostics-1",
            ShellEngineeringLoopOperation.RUNTIME_DIAGNOSTICS,
            runtime_diagnostic_requests=(diagnostic_request,),
            runtime_diagnostics=(diagnostic_receipt,),
        ),
        ShellEngineeringLoopQuery(
            "loop-database-1", ShellEngineeringLoopOperation.DATABASE,
            grant.owner_id, "task-1",
        ),
        ShellEngineeringLoopResponse(
            "loop-database-1", ShellEngineeringLoopOperation.DATABASE,
            database_plans=(database_plan,),
            database_backups=(database_backup,),
            database_verifications=(database_receipt,),
            database_postapply=(database_postapply,),
        ),
        ShellEngineeringCandidateEditRequest(
            "loop-edit-1", grant.owner_id, "task-1", "edit-1",
            "session-1", grant.principal_id,
            CandidateOperation(
                "candidate-edit-1", CandidateOperationKind.CREATE_FILE,
                "src/generated.py", artifact_id=edit_artifact.artifact_id,
            ),
            edit_artifact, base64.b64encode(edit_content).decode(), True,
        ),
        ShellEngineeringCandidateVerificationRequest(
            "loop-verify-1", grant.owner_id, "task-1", "verification-1",
            "session-1", grant.principal_id, "python3",
            "engineering.python.test", "1.0.0", True,
        ),
        ShellEngineeringCandidateReverificationRequest(
            "loop-reverify-1", grant.owner_id, "task-1", "verification-2",
            "session-1", grant.principal_id, "python3",
            "engineering.python.test", "1.0.0", True,
        ),
        ShellEngineeringChangesetPreviewRequest(
            "loop-preview-1", grant.owner_id, "task-1",
            changeset.changeset_id, True,
        ),
        ShellEngineeringChangesetApplyRequest(
            "loop-apply-1", grant.owner_id, "task-1",
            changeset.changeset_id, changeset.decision,
            "session-1", grant.principal_id, True,
        ),
        ShellEngineeringPublicationRequest(
            "loop-publish-1", grant.owner_id,
            publication_approval.task_id, publication_approval, True,
        ),
        ShellEngineeringIncidentAdvanceRequest(
            "loop-incident-1", grant.owner_id, "task-1", "incident-1",
            EngineeringIncidentStage.EVIDENCE_PRESERVED,
            "preservation-receipt-1", True,
        ),
        ShellEngineeringContextRequest(
            "engineering-context-1", "authority-session-1", grant.owner_id,
            "engineering-grant", grant_approval.grant_sha256, True,
        ),
        ShellEngineeringActivationRequest(
            "engineering-activate-1", "authority-session-1", grant,
            grant_approval, challenge, break_glass, True,
        ),
        ShellEngineeringGrantQuery(
            "engineering-query-1", ShellEngineeringAuthorityOperation.INSPECT,
            grant.grant_id,
        ),
        ShellEngineeringRevocationRequest(
            "engineering-revoke-1", grant.grant_id, grant.owner_id, True,
        ),
        ShellEngineeringAuthorityResponse(
            "engineering-query-1", ShellEngineeringAuthorityOperation.INSPECT,
            grant=grant, reconfirmation_required=False, usable=True,
        ),
    )
