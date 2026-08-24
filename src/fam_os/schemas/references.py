"""Cross-document reference validation after strict per-document decoding."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.applications import ConnectorManifest
from fam_os.core.contracts import ExecutionPlan, TaskRequest, TaskResult
from fam_os.core.engineering import (
    BreakGlassChallenge,
    BreakGlassDecision,
    ChangeSetProposal,
    CheckpointDecision,
    DependencyPlan,
    DesignAssetManifest,
    EngineeringEvidence,
    EngineeringCapabilityUnavailable,
    EngineeringAuthorityGrant,
    EngineeringAuthorizationDecision,
    EngineeringAuthorizationRequest,
    EngineeringExecutionRecord,
    EngineeringGrantScopeKind,
    EngineeringProposalResult,
    EngineeringPublicationProposal,
    EngineeringPublicationReceipt,
    EngineeringTaskEnvelope,
    GitOperation,
    OwnerGrantApproval,
    ToolRecipe,
    ToolRun,
    WorkspaceSnapshot,
    VerifiedChangeSetReceipt,
    CandidateApplyReceipt,
    CandidateArtifact,
    CandidateOperation,
    CandidateTransactionPreview,
    CandidateWorkspace,
    DependencyResolutionReceipt,
    DependencyResolutionRequest,
    EngineeringToolReceipt,
    HostAdministrationChangeSet,
    HostAdministrationReceipt,
    LanguageToolQualification,
    RawShellAuthorization,
    SecretUseAuthorization,
    SecretUseReceipt,
    SignedToolRecipe,
)
from fam_os.experts import ExpertManifest
from fam_os.core.engineering.repository import (
    ArchitectureProposal,
    EngineeringTaskGraph,
    EngineeringTaskGraphEvent,
    RepositoryAnalysis,
    RepositoryAnalysisRequest,
    RepositoryEvidenceBundle,
)
from fam_os.memory import MemoryRecordManifest
from fam_os.scheduler.resources import EffectiveResourceBudget, HostInventory
from fam_os.schemas.errors import CrossContractValidationError
from fam_os.verification import VerifierManifest


@dataclass(frozen=True, slots=True)
class ReferenceIssue:
    code: str
    source_id: str
    target_id: str
    safe_message: str


@dataclass(frozen=True, slots=True)
class ContractReferenceSet:
    requests: tuple[TaskRequest, ...] = ()
    plans: tuple[ExecutionPlan, ...] = ()
    results: tuple[TaskResult, ...] = ()
    inventories: tuple[HostInventory, ...] = ()
    budgets: tuple[EffectiveResourceBudget, ...] = ()
    experts: tuple[ExpertManifest, ...] = ()
    verifiers: tuple[VerifierManifest, ...] = ()
    connectors: tuple[ConnectorManifest, ...] = ()
    memory_records: tuple[MemoryRecordManifest, ...] = ()
    engineering_tasks: tuple[EngineeringTaskEnvelope, ...] = ()
    workspace_snapshots: tuple[WorkspaceSnapshot, ...] = ()
    change_sets: tuple[ChangeSetProposal, ...] = ()
    tool_recipes: tuple[ToolRecipe, ...] = ()
    tool_runs: tuple[ToolRun, ...] = ()
    dependency_plans: tuple[DependencyPlan, ...] = ()
    design_manifests: tuple[DesignAssetManifest, ...] = ()
    git_operations: tuple[GitOperation, ...] = ()
    checkpoint_decisions: tuple[CheckpointDecision, ...] = ()
    engineering_evidence: tuple[EngineeringEvidence, ...] = ()
    engineering_proposal_results: tuple[EngineeringProposalResult, ...] = ()
    verified_change_set_receipts: tuple[VerifiedChangeSetReceipt, ...] = ()
    publication_proposals: tuple[EngineeringPublicationProposal, ...] = ()
    publication_receipts: tuple[EngineeringPublicationReceipt, ...] = ()
    unavailable_results: tuple[EngineeringCapabilityUnavailable, ...] = ()
    engineering_grants: tuple[EngineeringAuthorityGrant, ...] = ()
    owner_grant_approvals: tuple[OwnerGrantApproval, ...] = ()
    engineering_authorization_requests: tuple[EngineeringAuthorizationRequest, ...] = ()
    engineering_authorization_decisions: tuple[EngineeringAuthorizationDecision, ...] = ()
    break_glass_challenges: tuple[BreakGlassChallenge, ...] = ()
    break_glass_decisions: tuple[BreakGlassDecision, ...] = ()
    engineering_execution_records: tuple[EngineeringExecutionRecord, ...] = ()
    repository_evidence_bundles: tuple[RepositoryEvidenceBundle, ...] = ()
    repository_analysis_requests: tuple[RepositoryAnalysisRequest, ...] = ()
    repository_analyses: tuple[RepositoryAnalysis, ...] = ()
    architecture_proposals: tuple[ArchitectureProposal, ...] = ()
    engineering_task_graphs: tuple[EngineeringTaskGraph, ...] = ()
    engineering_task_graph_events: tuple[EngineeringTaskGraphEvent, ...] = ()
    candidate_artifacts: tuple[CandidateArtifact, ...] = ()
    candidate_operations: tuple[CandidateOperation, ...] = ()
    candidate_workspaces: tuple[CandidateWorkspace, ...] = ()
    candidate_transaction_previews: tuple[CandidateTransactionPreview, ...] = ()
    candidate_apply_receipts: tuple[CandidateApplyReceipt, ...] = ()
    signed_tool_recipes: tuple[SignedToolRecipe, ...] = ()
    raw_shell_authorizations: tuple[RawShellAuthorization, ...] = ()
    engineering_tool_receipts: tuple[EngineeringToolReceipt, ...] = ()
    language_tool_qualifications: tuple[LanguageToolQualification, ...] = ()
    dependency_resolution_requests: tuple[DependencyResolutionRequest, ...] = ()
    dependency_resolution_receipts: tuple[DependencyResolutionReceipt, ...] = ()
    host_administration_change_sets: tuple[HostAdministrationChangeSet, ...] = ()
    host_administration_receipts: tuple[HostAdministrationReceipt, ...] = ()
    secret_use_authorizations: tuple[SecretUseAuthorization, ...] = ()
    secret_use_receipts: tuple[SecretUseReceipt, ...] = ()
    known_schema_ids: frozenset[str] = frozenset()


def find_reference_issues(references: ContractReferenceSet) -> tuple[ReferenceIssue, ...]:
    issues: list[ReferenceIssue] = []
    issues.extend(_identity_issues(references))
    issues.extend(_core_issues(references))
    issues.extend(_hardware_issues(references))
    issues.extend(_manifest_issues(references))
    issues.extend(_memory_issues(references))
    issues.extend(_engineering_issues(references))
    issues.extend(_engineering_grant_issues(references))
    issues.extend(_repository_intelligence_issues(references))
    issues.extend(_candidate_transaction_issues(references))
    issues.extend(_engineering_execution_issues(references))
    return tuple(issues)


def require_valid_references(references: ContractReferenceSet) -> None:
    issues = find_reference_issues(references)
    if issues:
        raise CrossContractValidationError(tuple(issue.code for issue in issues))


def _identity_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    groups = (
        (refs.requests, "request_id", "core.request.duplicate"),
        (refs.plans, "plan_id", "core.plan.duplicate"),
        (refs.inventories, "inventory_id", "hardware.inventory.duplicate"),
        (refs.budgets, "budget_id", "hardware.budget.duplicate"),
        (refs.experts, "expert_id", "expert.manifest.duplicate"),
        (refs.verifiers, "verifier_id", "verifier.manifest.duplicate"),
        (refs.connectors, "connector_id", "connector.manifest.duplicate"),
        (refs.memory_records, "record_id", "memory.record.duplicate"),
        (refs.engineering_tasks, "task_id", "engineering.task.duplicate"),
        (refs.workspace_snapshots, "snapshot_id", "engineering.snapshot.duplicate"),
        (refs.change_sets, "proposal_id", "engineering.change_set.duplicate"),
        (refs.tool_recipes, "recipe_id", "engineering.tool_recipe.duplicate"),
        (refs.tool_runs, "run_id", "engineering.tool_run.duplicate"),
        (refs.dependency_plans, "plan_id", "engineering.dependency_plan.duplicate"),
        (refs.design_manifests, "manifest_id", "engineering.design_manifest.duplicate"),
        (refs.git_operations, "operation_id", "engineering.git_operation.duplicate"),
        (refs.checkpoint_decisions, "decision_id", "engineering.checkpoint.duplicate"),
        (refs.engineering_evidence, "evidence_id", "engineering.evidence.duplicate"),
        (refs.engineering_proposal_results, "result_id", "engineering.proposal_result.duplicate"),
        (refs.verified_change_set_receipts, "receipt_id", "engineering.change_receipt.duplicate"),
        (refs.publication_proposals, "proposal_id", "engineering.publication_proposal.duplicate"),
        (refs.publication_receipts, "receipt_id", "engineering.publication_receipt.duplicate"),
        (refs.unavailable_results, "result_id", "engineering.unavailable.duplicate"),
        (refs.engineering_grants, "grant_id", "engineering.grant.duplicate"),
        (refs.owner_grant_approvals, "approval_id", "engineering.grant_approval.duplicate"),
        (refs.engineering_authorization_requests, "request_id", "engineering.authorization_request.duplicate"),
        (refs.engineering_authorization_decisions, "decision_id", "engineering.authorization_decision.duplicate"),
        (refs.break_glass_challenges, "challenge_id", "engineering.break_glass.duplicate"),
        (refs.break_glass_decisions, "decision_id", "engineering.break_glass_decision.duplicate"),
        (refs.engineering_execution_records, "record_id", "engineering.execution.duplicate"),
        (refs.repository_evidence_bundles, "bundle_id", "engineering.repository_evidence.duplicate"),
        (refs.repository_analysis_requests, "request_id", "engineering.repository_request.duplicate"),
        (refs.repository_analyses, "analysis_id", "engineering.repository_analysis.duplicate"),
        (refs.architecture_proposals, "proposal_id", "engineering.architecture_proposal.duplicate"),
        (refs.engineering_task_graphs, "graph_id", "engineering.task_graph.duplicate"),
        (refs.engineering_task_graph_events, "event_id", "engineering.task_graph_event.duplicate"),
        (refs.candidate_artifacts, "artifact_id", "engineering.candidate_artifact.duplicate"),
        (refs.candidate_operations, "operation_id", "engineering.candidate_operation.duplicate"),
        (refs.candidate_workspaces, "candidate_id", "engineering.candidate_workspace.duplicate"),
        (refs.candidate_transaction_previews, "transaction_id", "engineering.candidate_preview.duplicate"),
        (refs.candidate_apply_receipts, "transaction_id", "engineering.candidate_receipt.duplicate"),
        (refs.signed_tool_recipes, "recipe_id", "engineering.signed_recipe.duplicate"),
        (refs.raw_shell_authorizations, "authorization_id", "engineering.raw_shell.duplicate"),
        (refs.engineering_tool_receipts, "receipt_id", "engineering.tool_receipt.duplicate"),
        (refs.language_tool_qualifications, "qualification_id", "engineering.language_qualification.duplicate"),
        (refs.dependency_resolution_requests, "request_id", "engineering.dependency_request.duplicate"),
        (refs.dependency_resolution_receipts, "receipt_id", "engineering.dependency_receipt.duplicate"),
        (refs.host_administration_change_sets, "change_set_id", "engineering.host_change.duplicate"),
        (refs.host_administration_receipts, "receipt_id", "engineering.host_receipt.duplicate"),
        (refs.secret_use_authorizations, "authorization_id", "engineering.secret_authorization.duplicate"),
        (refs.secret_use_receipts, "receipt_id", "engineering.secret_receipt.duplicate"),
    )
    issues: list[ReferenceIssue] = []
    for items, attribute, code in groups:
        values = tuple(getattr(item, attribute) for item in items)
        duplicates = sorted(value for value in set(values) if values.count(value) > 1)
        issues.extend(_issue(code, value, value) for value in duplicates)
    return issues


def _core_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    requests = {item.request_id: item for item in refs.requests}
    plans = {item.plan_id: item for item in refs.plans}
    for plan in refs.plans:
        if plan.request_id not in requests:
            issues.append(_issue("core.plan.request_missing", plan.plan_id, plan.request_id))
    for result in refs.results:
        if result.request_id not in requests:
            issues.append(_issue("core.result.request_missing", result.request_id, result.request_id))
        if result.plan_id is None:
            continue
        plan = plans.get(result.plan_id)
        if plan is None:
            issues.append(_issue("core.result.plan_missing", result.request_id, result.plan_id))
        elif plan.request_id != result.request_id:
            issues.append(_issue("core.result.plan_request_mismatch", result.request_id, plan.request_id))
    return issues


def _hardware_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    inventories = {item.inventory_id: item for item in refs.inventories}
    for budget in refs.budgets:
        inventory = inventories.get(budget.inventory_id)
        if inventory is None:
            issues.append(_issue("hardware.budget.inventory_missing", budget.budget_id, budget.inventory_id))
            continue
        accelerator_ids = {item.device_id for item in inventory.accelerators}
        storage = {item.storage_id: item for item in inventory.storage}
        for item in budget.accelerators:
            if item.device_id not in accelerator_ids:
                issues.append(_issue("hardware.budget.accelerator_missing", budget.budget_id, item.device_id))
        for item in budget.storage:
            inventory_storage = storage.get(item.storage_id)
            if inventory_storage is None:
                issues.append(_issue("hardware.budget.storage_missing", budget.budget_id, item.storage_id))
            elif item.scheduler_cache_limit_bytes and not inventory_storage.cache_eligible:
                issues.append(_issue("hardware.budget.storage_not_cache_eligible", budget.budget_id, item.storage_id))
    return issues


def _manifest_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    verifier_ids = {item.verifier_id for item in refs.verifiers}
    known_schemas = refs.known_schema_ids
    for expert in refs.experts:
        for verifier_id in expert.required_verifier_ids:
            if verifier_id not in verifier_ids:
                issues.append(_issue("expert.verifier_missing", expert.expert_id, verifier_id))
    for verifier in refs.verifiers:
        schema_ids = (*verifier.candidate_schema_ids, verifier.evidence_schema_id)
        issues.extend(_schema_issues("verifier.schema_missing", verifier.verifier_id, schema_ids, known_schemas))
    for connector in refs.connectors:
        for capability in connector.capabilities:
            schema_ids = (capability.input_schema_id, capability.output_schema_id)
            issues.extend(_schema_issues("connector.schema_missing", connector.connector_id, schema_ids, known_schemas))
    return issues


def _memory_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    record_ids = {item.record_id for item in refs.memory_records}
    for record in refs.memory_records:
        if record.content_schema_id not in refs.known_schema_ids:
            issues.append(
                _issue("memory.content_schema_missing", record.record_id, record.content_schema_id)
            )
        for parent_id in record.provenance.parent_record_ids:
            if parent_id not in record_ids:
                issues.append(_issue("memory.parent_missing", record.record_id, parent_id))
    return issues


def _engineering_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    task_ids = {item.task_id for item in refs.engineering_tasks}
    snapshots = {item.snapshot_id: item for item in refs.workspace_snapshots}
    proposals = {item.proposal_id: item for item in refs.change_sets}
    publication_proposals = {
        item.proposal_id: item for item in refs.publication_proposals
    }
    recipes = {item.recipe_id: item for item in refs.tool_recipes}
    runs = {item.run_id: item for item in refs.tool_runs}
    decisions = {item.decision_id: item for item in refs.checkpoint_decisions}
    task_bound = (
        *refs.workspace_snapshots, *refs.change_sets, *refs.tool_recipes,
        *refs.tool_runs, *refs.dependency_plans, *refs.design_manifests,
        *refs.git_operations, *refs.checkpoint_decisions, *refs.engineering_evidence,
        *refs.engineering_proposal_results, *refs.verified_change_set_receipts,
        *refs.publication_proposals, *refs.publication_receipts,
        *refs.unavailable_results,
    )
    for item in task_bound:
        if item.task_id not in task_ids:
            issues.append(_issue("engineering.task.missing", _engineering_id(item), item.task_id))
    for proposal in refs.change_sets:
        snapshot = snapshots.get(proposal.snapshot_id)
        if snapshot is None:
            issues.append(_issue("engineering.change_set.snapshot_missing", proposal.proposal_id, proposal.snapshot_id))
        elif snapshot.task_id != proposal.task_id:
            issues.append(_issue("engineering.change_set.task_mismatch", proposal.proposal_id, snapshot.task_id))
    for run in refs.tool_runs:
        recipe = recipes.get(run.recipe_id)
        if recipe is None:
            issues.append(_issue("engineering.tool_run.recipe_missing", run.run_id, run.recipe_id))
        elif recipe.task_id != run.task_id:
            issues.append(_issue("engineering.tool_run.task_mismatch", run.run_id, recipe.task_id))
    for decision in refs.checkpoint_decisions:
        proposal = proposals.get(decision.proposal_id) or publication_proposals.get(
            decision.proposal_id
        )
        if proposal is None:
            issues.append(_issue("engineering.checkpoint.proposal_missing", decision.decision_id, decision.proposal_id))
        elif proposal.task_id != decision.task_id:
            issues.append(_issue("engineering.checkpoint.task_mismatch", decision.decision_id, proposal.task_id))
    for evidence in refs.engineering_evidence:
        issues.extend(_reference_ids(
            "engineering.evidence.snapshot_missing", evidence.evidence_id,
            evidence.snapshot_ids, snapshots,
        ))
        issues.extend(_reference_ids(
            "engineering.evidence.proposal_missing", evidence.evidence_id,
            evidence.proposal_ids, proposals,
        ))
        issues.extend(_reference_ids(
            "engineering.evidence.checkpoint_missing", evidence.evidence_id,
            evidence.checkpoint_decision_ids, decisions,
        ))
        issues.extend(_reference_ids(
            "engineering.evidence.tool_run_missing", evidence.evidence_id,
            evidence.tool_run_ids, runs,
        ))
    for result in refs.engineering_proposal_results:
        if result.change_set_proposal_id not in proposals:
            issues.append(_issue(
                "engineering.proposal_result.change_set_missing", result.result_id,
                result.change_set_proposal_id,
            ))
    for receipt in refs.verified_change_set_receipts:
        if receipt.proposal_id not in proposals:
            issues.append(_issue(
                "engineering.change_receipt.proposal_missing", receipt.receipt_id,
                receipt.proposal_id,
            ))
        issues.extend(_reference_ids(
            "engineering.change_receipt.snapshot_missing", receipt.receipt_id,
            (receipt.before_snapshot_id, receipt.after_snapshot_id), snapshots,
        ))
        issues.extend(_reference_ids(
            "engineering.change_receipt.tool_run_missing", receipt.receipt_id,
            receipt.tool_run_ids, runs,
        ))
    for receipt in refs.publication_receipts:
        publication_proposal = publication_proposals.get(receipt.publication_proposal_id)
        if publication_proposal is None:
            issues.append(_issue(
                "engineering.publication_receipt.proposal_missing", receipt.receipt_id,
                receipt.publication_proposal_id,
            ))
        decision = decisions.get(receipt.checkpoint_decision_id)
        if decision is None:
            issues.append(_issue(
                "engineering.publication_receipt.checkpoint_missing", receipt.receipt_id,
                receipt.checkpoint_decision_id,
            ))
        elif decision.proposal_id != receipt.publication_proposal_id:
            issues.append(_issue(
                "engineering.publication_receipt.checkpoint_mismatch", receipt.receipt_id,
                decision.proposal_id,
            ))
    return issues


def _engineering_grant_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    task_ids = {item.task_id for item in refs.engineering_tasks}
    grants = {item.grant_id: item for item in refs.engineering_grants}
    requests = {
        item.request_id: item for item in refs.engineering_authorization_requests
    }
    challenges = {
        item.challenge_id: item for item in refs.break_glass_challenges
    }
    decisions = {item.decision_id: item for item in refs.break_glass_decisions}
    for grant in refs.engineering_grants:
        if (
            grant.scope.kind is EngineeringGrantScopeKind.TASK
            and grant.scope.scope_id not in task_ids
        ):
            issues.append(_issue(
                "engineering.grant.task_missing", grant.grant_id,
                grant.scope.scope_id,
            ))
    for approval in refs.owner_grant_approvals:
        grant = grants.get(approval.grant_id)
        if grant is None:
            issues.append(_issue(
                "engineering.grant_approval.grant_missing", approval.approval_id,
                approval.grant_id,
            ))
        elif grant.owner_id != approval.owner_id:
            issues.append(_issue(
                "engineering.grant_approval.owner_mismatch", approval.approval_id,
                approval.owner_id,
            ))
    for challenge in refs.break_glass_challenges:
        if challenge.grant_id not in grants:
            issues.append(_issue(
                "engineering.break_glass.grant_missing", challenge.challenge_id,
                challenge.grant_id,
            ))
    for decision in refs.break_glass_decisions:
        challenge = challenges.get(decision.challenge_id)
        if challenge is None:
            issues.append(_issue(
                "engineering.break_glass_decision.challenge_missing",
                decision.decision_id, decision.challenge_id,
            ))
        elif (
            decision.grant_id != challenge.grant_id
            or decision.owner_id != challenge.owner_id
        ):
            issues.append(_issue(
                "engineering.break_glass_decision.challenge_mismatch",
                decision.decision_id, decision.challenge_id,
            ))
    for request in refs.engineering_authorization_requests:
        if request.grant_id not in grants:
            issues.append(_issue(
                "engineering.authorization_request.grant_missing",
                request.request_id, request.grant_id,
            ))
    for decision in refs.engineering_authorization_decisions:
        request = requests.get(decision.request_id)
        if request is None:
            issues.append(_issue(
                "engineering.authorization_decision.request_missing",
                decision.decision_id, decision.request_id,
            ))
        elif (
            decision.grant_id != request.grant_id
            or decision.authority is not request.authority
        ):
            issues.append(_issue(
                "engineering.authorization_decision.request_mismatch",
                decision.decision_id, decision.request_id,
            ))
    for record in refs.engineering_execution_records:
        if record.task_id not in task_ids:
            issues.append(_issue(
                "engineering.execution.task_missing", record.record_id,
                record.task_id,
            ))
        if record.grant_id not in grants:
            issues.append(_issue(
                "engineering.execution.grant_missing", record.record_id,
                record.grant_id,
            ))
        if (
            record.waiver_decision_id is not None
            and record.waiver_decision_id not in decisions
        ):
            issues.append(_issue(
                "engineering.execution.waiver_missing", record.record_id,
                record.waiver_decision_id,
            ))
    return issues


def _engineering_id(value: object) -> str:
    for name in ("snapshot_id", "proposal_id", "recipe_id", "run_id", "plan_id",
                 "manifest_id", "operation_id", "decision_id", "evidence_id",
                 "result_id", "receipt_id", "authorization_id", "request_id",
                 "change_set_id"):
        identifier = getattr(value, name, None)
        if isinstance(identifier, str):
            return identifier
    raise ValueError("engineering contract has no public identity")


def _repository_intelligence_issues(
    refs: ContractReferenceSet,
) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    task_ids = {item.task_id for item in refs.engineering_tasks}
    bundles = {item.bundle_id: item for item in refs.repository_evidence_bundles}
    requests = {
        item.request_id: item for item in refs.repository_analysis_requests
    }
    analyses = {item.analysis_id: item for item in refs.repository_analyses}
    graphs = {item.graph_id: item for item in refs.engineering_task_graphs}
    task_bound = (
        *refs.repository_evidence_bundles, *refs.repository_analysis_requests,
        *refs.repository_analyses, *refs.architecture_proposals,
        *refs.engineering_task_graphs, *refs.engineering_task_graph_events,
    )
    for item in task_bound:
        if item.task_id not in task_ids:
            issues.append(_issue(
                "engineering.repository.task_missing", _repository_id(item),
                item.task_id,
            ))
    for analysis in refs.repository_analyses:
        request = requests.get(analysis.request_id)
        bundle = bundles.get(analysis.bundle_id)
        if request is None:
            issues.append(_issue(
                "engineering.repository_analysis.request_missing",
                analysis.analysis_id, analysis.request_id,
            ))
        if bundle is None:
            issues.append(_issue(
                "engineering.repository_analysis.bundle_missing",
                analysis.analysis_id, analysis.bundle_id,
            ))
        if request is not None and request.task_id != analysis.task_id:
            issues.append(_issue(
                "engineering.repository_analysis.task_mismatch",
                analysis.analysis_id, request.task_id,
            ))
    for proposal in refs.architecture_proposals:
        analysis = analyses.get(proposal.analysis_id)
        if analysis is None:
            issues.append(_issue(
                "engineering.architecture.analysis_missing", proposal.proposal_id,
                proposal.analysis_id,
            ))
        elif analysis.task_id != proposal.task_id:
            issues.append(_issue(
                "engineering.architecture.task_mismatch", proposal.proposal_id,
                analysis.task_id,
            ))
    for event in refs.engineering_task_graph_events:
        graph = graphs.get(event.graph_id)
        if graph is None:
            issues.append(_issue(
                "engineering.task_graph_event.graph_missing", event.event_id,
                event.graph_id,
            ))
        elif (
            graph.task_id != event.task_id
            or event.step_id not in {step.step_id for step in graph.steps}
        ):
            issues.append(_issue(
                "engineering.task_graph_event.graph_mismatch", event.event_id,
                event.graph_id,
            ))
    return issues


def _repository_id(value: object) -> str:
    for name in (
        "bundle_id", "request_id", "analysis_id", "proposal_id", "graph_id",
        "event_id",
    ):
        identifier = getattr(value, name, None)
        if isinstance(identifier, str):
            return identifier
    raise ValueError("repository intelligence contract has no public identity")


def _candidate_transaction_issues(
    refs: ContractReferenceSet,
) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    task_ids = {item.task_id for item in refs.engineering_tasks}
    artifacts = {item.artifact_id for item in refs.candidate_artifacts}
    candidates = {item.candidate_id: item for item in refs.candidate_workspaces}
    previews = {
        item.transaction_id: item for item in refs.candidate_transaction_previews
    }
    for candidate in refs.candidate_workspaces:
        if candidate.task_id not in task_ids:
            issues.append(_issue(
                "engineering.candidate.task_missing", candidate.candidate_id,
                candidate.task_id,
            ))
    for operation in refs.candidate_operations:
        if operation.artifact_id is not None and operation.artifact_id not in artifacts:
            issues.append(_issue(
                "engineering.candidate_operation.artifact_missing",
                operation.operation_id, operation.artifact_id,
            ))
    for preview in refs.candidate_transaction_previews:
        candidate = candidates.get(preview.candidate_id)
        if candidate is None:
            issues.append(_issue(
                "engineering.candidate_preview.workspace_missing",
                preview.transaction_id, preview.candidate_id,
            ))
        elif candidate.baseline_tree_sha256 != preview.baseline_tree_sha256:
            issues.append(_issue(
                "engineering.candidate_preview.baseline_mismatch",
                preview.transaction_id, preview.candidate_id,
            ))
    for receipt in refs.candidate_apply_receipts:
        preview = previews.get(receipt.transaction_id)
        if preview is None:
            issues.append(_issue(
                "engineering.candidate_receipt.preview_missing",
                receipt.transaction_id, receipt.transaction_id,
            ))
        elif preview.candidate_id != receipt.candidate_id:
            issues.append(_issue(
                "engineering.candidate_receipt.workspace_mismatch",
                receipt.transaction_id, receipt.candidate_id,
            ))
    return issues


def _engineering_execution_issues(
    refs: ContractReferenceSet,
) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    tasks = {item.task_id for item in refs.engineering_tasks}
    grants = {item.grant_id for item in refs.engineering_grants}
    candidates = {item.candidate_id for item in refs.candidate_workspaces}
    recipes = {item.recipe_id for item in refs.signed_tool_recipes}
    dependency_requests = {
        item.request_id: item for item in refs.dependency_resolution_requests
    }
    host_changes = {
        item.change_set_id for item in refs.host_administration_change_sets
    }
    secret_authorizations = {
        item.authorization_id: item for item in refs.secret_use_authorizations
    }
    for item in (
        *refs.raw_shell_authorizations, *refs.engineering_tool_receipts,
        *refs.dependency_resolution_requests, *refs.dependency_resolution_receipts,
        *refs.host_administration_change_sets, *refs.secret_use_authorizations,
    ):
        if item.task_id not in tasks:
            issues.append(_issue(
                "engineering.execution.task_missing", _engineering_id(item),
                item.task_id,
            ))
    for authorization in refs.raw_shell_authorizations:
        if authorization.grant_id not in grants:
            issues.append(_issue(
                "engineering.raw_shell.grant_missing",
                authorization.authorization_id, authorization.grant_id,
            ))
    for receipt in refs.engineering_tool_receipts:
        if receipt.candidate_id not in candidates:
            issues.append(_issue(
                "engineering.tool_receipt.candidate_missing", receipt.receipt_id,
                receipt.candidate_id,
            ))
        if receipt.recipe_id not in recipes:
            issues.append(_issue(
                "engineering.tool_receipt.recipe_missing", receipt.receipt_id,
                receipt.recipe_id,
            ))
    for receipt in refs.dependency_resolution_receipts:
        request = dependency_requests.get(receipt.request_id)
        if request is None:
            issues.append(_issue(
                "engineering.dependency_receipt.request_missing",
                receipt.receipt_id, receipt.request_id,
            ))
        elif request.candidate_id != receipt.candidate_id:
            issues.append(_issue(
                "engineering.dependency_receipt.candidate_mismatch",
                receipt.receipt_id, receipt.candidate_id,
            ))
    for receipt in refs.host_administration_receipts:
        if receipt.change_set_id not in host_changes:
            issues.append(_issue(
                "engineering.host_receipt.change_missing", receipt.receipt_id,
                receipt.change_set_id,
            ))
    for receipt in refs.secret_use_receipts:
        authorization = secret_authorizations.get(receipt.authorization_id)
        if authorization is None:
            issues.append(_issue(
                "engineering.secret_receipt.authorization_missing",
                receipt.receipt_id, receipt.authorization_id,
            ))
        elif (
            authorization.secret_ref != receipt.secret_ref
            or authorization.level is not receipt.level
        ):
            issues.append(_issue(
                "engineering.secret_receipt.authorization_mismatch",
                receipt.receipt_id, receipt.authorization_id,
            ))
    return issues


def _reference_ids(
    code: str, source_id: str, target_ids: tuple[str, ...], known: dict[str, object],
) -> list[ReferenceIssue]:
    return [_issue(code, source_id, target_id) for target_id in target_ids if target_id not in known]


def _schema_issues(
    code: str, source_id: str, schema_ids: tuple[str, ...], known: frozenset[str]
) -> list[ReferenceIssue]:
    return [_issue(code, source_id, schema_id) for schema_id in schema_ids if schema_id not in known]


def _issue(code: str, source_id: str, target_id: str) -> ReferenceIssue:
    return ReferenceIssue(code, source_id, target_id, "A referenced contract object is unavailable.")
