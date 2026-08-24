"""Owner-scoped product facade for the persistent master engineering loop."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.sqlite import (
    SQLiteCandidateEditStore, SQLiteEngineeringLoopStore,
    SQLiteEngineeringPreparationStore,
    SQLiteCandidateVerificationStore,
    SQLiteCandidateChangesetStore,
)
from fam_os.adapters.filesystem import (
    BoundedFilesystemRepositoryObserver, CandidateWorkspaceAdapter,
)
from fam_os.console.engineering import project_engineering_task
from fam_os.core.engineering import (
    EngineeringLoopBudget,
    EngineeringLoopStage,
    EngineeringGrantScopeKind,
    EngineeringLifecycleDriver,
    EngineeringTaskDefinition,
    MasterEngineeringLoop,
    EngineeringPreparationOrchestrator,
    EngineeringEvidence,
    EngineeringOutcome,
    CandidateArtifact,
    CandidateOperation,
    CandidateVerificationService,
    ToolRecipePurpose,
    GitPublicationApproval,
    IntegrationEnvironmentStatus,
    integration_environment_plan_digest,
    natural_integration_environment_requested,
)
from fam_os.core.engineering.repository import BoundedRepositoryPlanner, RepositoryAnalysisRequest
from fam_os.product.storage.engineering_grant_repository import (
    SqliteEngineeringGrantRepository,
)
from fam_os.product.candidate_engineering_api import ProductCandidateEngineeringApi
from fam_os.product.git_publication_api import ProductGitPublicationApi
from fam_os.product.engineering_incident_api import ProductEngineeringIncidentApi
from fam_os.product.engineering_review_api import ProductEngineeringReviewApi
from fam_os.product.engineering_documentation_api import ProductEngineeringDocumentationApi
from fam_os.product.runtime_diagnostic_api import ProductRuntimeDiagnosticApi
from fam_os.product.database_engineering_api import ProductDatabaseEngineeringApi


class ProductEngineeringLoopApi:
    """Expose lifecycle state without granting any underlying engineering effect."""

    def __init__(
        self,
        owner_id: str,
        grants: SqliteEngineeringGrantRepository,
        store: SQLiteEngineeringLoopStore,
        candidate_root: Path,
        preparations: SQLiteEngineeringPreparationStore,
        authorizer=None,
        edits: SQLiteCandidateEditStore | None = None,
        verification_service: CandidateVerificationService | None = None,
        verifications: SQLiteCandidateVerificationStore | None = None,
        changesets: SQLiteCandidateChangesetStore | None = None,
        recipe_catalog=None,
        git_delivery=None,
        publication_service=None,
        incident_service=None,
        review_service=None,
        documentation_store=None,
        documentation_recipes=None,
        runtime_diagnostic_service=None,
        runtime_diagnostic_store=None,
        database_builder=None,
        database_service=None,
        database_store=None,
    ) -> None:
        self.owner_id = owner_id
        self._grants = grants
        self._store = store
        self._loop = MasterEngineeringLoop(store)
        self._candidate_root = candidate_root
        self._preparations = preparations
        self._recipe_catalog = recipe_catalog
        self._git_delivery = git_delivery
        self.lifecycle = EngineeringLifecycleDriver(
            self._loop, self._validate_lifecycle_grant,
            self._validate_publication_approval,
        )
        self._candidates = ProductCandidateEngineeringApi(
            store, preparations, candidate_root, authorizer, edits,
            verification_service, verifications, changesets, self.lifecycle,
            self._require_owner, self._validate_lifecycle_grant,
        )
        self._publication = ProductGitPublicationApi(
            owner_id, grants, store, self._candidates, git_delivery,
            publication_service, self.lifecycle,
        )
        self._incidents = ProductEngineeringIncidentApi(
            owner_id, store, incident_service,
        )
        self._reviews = ProductEngineeringReviewApi(
            owner_id, store, preparations, self._candidates, review_service,
        )
        self._documentation = ProductEngineeringDocumentationApi(
            owner_id, store, preparations, documentation_store,
            documentation_recipes,
        )
        self._runtime_diagnostics = ProductRuntimeDiagnosticApi(
            owner_id, store, preparations, candidate_root, recipe_catalog,
            runtime_diagnostic_service, runtime_diagnostic_store,
            self._require_owner, self._validate_lifecycle_grant,
        )
        self._databases = ProductDatabaseEngineeringApi(
            owner_id, store, preparations, candidate_root, database_builder,
            database_service, database_store, self.lifecycle,
            self._require_owner, self._validate_lifecycle_grant,
        )

    def start(
        self,
        owner_id: str,
        definition: EngineeringTaskDefinition,
        budget: EngineeringLoopBudget,
    ):
        self._require_owner(owner_id)
        task = definition.task
        if task.owner_id != owner_id:
            raise PermissionError("engineering task owner is invalid")
        grant = self._grants.usable(task.grant_id)
        instant = datetime.now(timezone.utc)
        if grant is None or grant.owner_id != owner_id or not grant.active_at(instant):
            raise PermissionError("engineering task requires a usable owner grant")
        _validate_task_grant(task, grant, instant)
        return self._loop.start_defined(definition, budget, instant=instant)

    def inspect(self, owner_id: str, task_id: str) -> dict:
        self._require_owner(owner_id)
        state = self._store.load(task_id)
        if state is None:
            raise KeyError("engineering task is unavailable")
        return _view(project_engineering_task(state), self._store.load_task(task_id))

    def tasks(self, owner_id: str) -> tuple[dict, ...]:
        self._require_owner(owner_id)
        return tuple(
            _view(project_engineering_task(state), self._store.load_task(state.task_id))
            for state in self._store.states()
        )

    def resume(self, owner_id: str, task_id: str) -> dict:
        self._require_owner(owner_id)
        state = self._loop.resume_after_restart(
            task_id, instant=datetime.now(timezone.utc),
        )
        return _view(project_engineering_task(state), self._store.load_task(task_id))

    def prepare(self, owner_id: str, task_id: str) -> dict:
        self._require_owner(owner_id)
        definition = self._store.load_task(task_id)
        if definition is None:
            raise KeyError("engineering task definition is unavailable")
        instant = datetime.now(timezone.utc)
        self._validate_lifecycle_grant(task_id, definition.task.grant_id, instant)
        if len(definition.task.workspace_roots) != 1:
            raise ValueError("single-repository preparation requires one workspace root")
        workspace = Path(definition.task.workspace_roots[0])
        candidates = CandidateWorkspaceAdapter(workspace, self._candidate_root)
        result = EngineeringPreparationOrchestrator(
            BoundedFilesystemRepositoryObserver(), BoundedRepositoryPlanner(),
            candidates, self.lifecycle, self._preparations,
        ).prepare(
            definition,
            RepositoryAnalysisRequest(
                f"analysis-{task_id}", task_id, definition.task.intent, (),
                128, 256, 128,
            ),
        )
        response = self.inspect(owner_id, task_id)
        response["repository_bundle_id"] = result.evidence.bundle_id
        response["architecture_proposal_id"] = result.proposal.proposal_id
        return response

    def preparation(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        result = self._preparations.load(task_id)
        if result is None:
            raise KeyError("engineering preparation is unavailable")
        return result

    def edit_candidate(
        self,
        owner_id: str,
        task_id: str,
        *,
        edit_id: str,
        session_id: str,
        principal_id: str,
        operation: CandidateOperation,
        artifact: CandidateArtifact | None = None,
        content: bytes | None = None,
    ):
        return self._candidates.edit(
            owner_id, task_id, edit_id=edit_id, session_id=session_id,
            principal_id=principal_id, operation=operation,
            artifact=artifact, content=content,
        )

    def candidate_edits(self, owner_id: str, task_id: str):
        return self._candidates.edits(owner_id, task_id)

    def verify_candidate(
        self, owner_id: str, task_id: str, *, verification_id: str,
        session_id: str, principal_id: str, toolchain: str,
        recipe_id: str, recipe_version: str, additional_budget=None,
        record_lifecycle: bool = True,
    ):
        return self._candidates.verify(
            owner_id, task_id, verification_id=verification_id,
            session_id=session_id, principal_id=principal_id,
            toolchain=toolchain, recipe_id=recipe_id,
            recipe_version=recipe_version, additional_budget=additional_budget,
            record_lifecycle=record_lifecycle,
        )

    def candidate_verifications(self, owner_id: str, task_id: str):
        return self._candidates.verifications(owner_id, task_id)

    def reverify_candidate(self, owner_id: str, task_id: str, **kwargs):
        return self._candidates.reverify(owner_id, task_id, **kwargs)

    def accept_candidate_verifications(
        self, owner_id: str, task_id: str, records, *, additional_budget=None,
    ) -> None:
        self._require_owner(owner_id)
        self._accept_verifications(
            task_id, records, additional_budget=additional_budget,
            postapply=False,
        )

    def accept_agent_verification(
        self, owner_id: str, task_id: str, turn_id: str,
        changed_paths: tuple[str, ...],
    ) -> str:
        """Record a successful model-selected sandbox check as lifecycle evidence."""
        self._require_owner(owner_id)
        identity = "\0".join((task_id, turn_id, *changed_paths))
        digest = hashlib.sha256(identity.encode()).hexdigest()
        evidence_id = f"agent-verification-{digest[:32]}"
        self.lifecycle.record_verification(EngineeringEvidence(
            evidence_id=evidence_id,
            task_id=task_id,
            recorded_at=datetime.now(timezone.utc),
            outcome=EngineeringOutcome.SUCCEEDED,
            snapshot_ids=(), proposal_ids=(), checkpoint_decision_ids=(),
            tool_run_ids=(turn_id,), verifier_run_ids=(turn_id,),
            artifact_sha256=(), changed_paths=changed_paths,
            unresolved_risks=(),
        ))
        return evidence_id

    def accept_agent_reverification(
        self, owner_id: str, task_id: str, turn_id: str,
        changed_paths: tuple[str, ...],
    ) -> str:
        """Record replay of a model-selected check against the applied workspace."""
        self._require_owner(owner_id)
        identity = "\0".join(("postapply", task_id, turn_id, *changed_paths))
        evidence_id = f"agent-reverification-{hashlib.sha256(identity.encode()).hexdigest()[:32]}"
        self.lifecycle.record_reverification(EngineeringEvidence(
            evidence_id=evidence_id,
            task_id=task_id,
            recorded_at=datetime.now(timezone.utc),
            outcome=EngineeringOutcome.SUCCEEDED,
            snapshot_ids=(), proposal_ids=(), checkpoint_decision_ids=(),
            tool_run_ids=(f"{turn_id}-postapply",),
            verifier_run_ids=(turn_id,), artifact_sha256=(),
            changed_paths=changed_paths, unresolved_risks=(),
        ))
        return evidence_id

    def accept_postapply_verifications(
        self, owner_id: str, task_id: str, records,
    ) -> None:
        self._require_owner(owner_id)
        self._accept_verifications(task_id, records, postapply=True)

    def preview_candidate(
        self, owner_id: str, task_id: str, changeset_id: str, *,
        verification_ids=None, runtime_diagnostic_receipt_ids=(),
        database_receipt_ids=(), integration_environment_evidence=(),
        postgresql_evidence=(), agent_verification_evidence_ids=(),
    ):
        selected = set(runtime_diagnostic_receipt_ids)
        diagnostics = tuple(
            item for item in self._runtime_diagnostics.receipts_for_task(
                owner_id, task_id,
            ) if item.receipt_id in selected
        )
        if {item.receipt_id for item in diagnostics} != selected:
            raise ValueError("runtime diagnostic receipt selection is incomplete")
        selected_database = set(database_receipt_ids)
        database_results = tuple(
            item for item in self._databases.results_for_task(owner_id, task_id)
            if item.verification.receipt_id in selected_database
        )
        if {
            item.verification.receipt_id for item in database_results
        } != selected_database:
            raise ValueError("database receipt selection is incomplete")
        return self._candidates.preview(
            owner_id, task_id, changeset_id,
            verification_ids=verification_ids,
            runtime_diagnostic_receipts=diagnostics,
            database_evidence=tuple(
                (item.plan, item.verification) for item in database_results
            ),
            integration_environment_evidence=integration_environment_evidence,
            postgresql_evidence=postgresql_evidence,
            agent_verification_evidence_ids=agent_verification_evidence_ids,
        )

    def current_candidate(self, owner_id: str, task_id: str):
        return self._candidates.current_candidate(owner_id, task_id)

    def apply_candidate(self, owner_id: str, task_id: str, changeset_id: str, decision, *, session_id: str, principal_id: str):
        changesets = tuple(
            item for item in self._candidates.changesets(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if len(changesets) != 1:
            raise KeyError("candidate changeset is unavailable")
        self._documentation.require_current(owner_id, task_id)
        self._reviews.require_passage(owner_id, task_id, changesets[0])
        return self._candidates.apply(
            owner_id, task_id, changeset_id, decision,
            session_id=session_id, principal_id=principal_id,
        )

    def candidate_changesets(self, owner_id: str, task_id: str):
        return self._candidates.changesets(owner_id, task_id)

    def commit_candidate(
        self, owner_id: str, task_id: str, changeset_id: str, *,
        session_id: str, principal_id: str, message: str,
    ):
        self._require_owner(owner_id)
        if self._git_delivery is None:
            raise RuntimeError("local Git delivery was not composed")
        definition = self._store.load_task(task_id)
        state = self._store.load(task_id)
        changesets = tuple(
            item for item in self._candidates.changesets(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if definition is None or state is None or len(changesets) != 1:
            raise KeyError("local Git delivery inputs are unavailable")
        if state.stage not in {
            EngineeringLoopStage.REVERIFIED, EngineeringLoopStage.COMMITTED,
        }:
            raise PermissionError("local Git commit requires reverified state")
        self._validate_lifecycle_grant(
            task_id, definition.task.grant_id, datetime.now(timezone.utc),
        )
        record = self._git_delivery.commit(
            definition, changesets[0], session_id=session_id,
            principal_id=principal_id,
            verification_evidence_ids=(
                *state.verification_receipt_ids,
                *state.runtime_diagnostic_receipt_ids,
                *state.database_receipt_ids,
                *state.database_postapply_receipt_ids,
                *state.integration_environment_receipt_ids,
                *state.integration_environment_postapply_receipt_ids,
            ),
            message=message,
        )
        if state.stage is EngineeringLoopStage.REVERIFIED:
            self.lifecycle.record_commit(
                task_id, record.commit_action, record.commit_receipt,
            )
        elif record.commit_receipt.receipt_id not in state.git_receipt_ids:
            raise RuntimeError("local Git lifecycle reconciliation conflicts")
        return record

    def rollback_checkpoint(
        self, owner_id: str, task_id: str, changeset_id: str,
    ) -> dict:
        self._require_owner(owner_id)
        if self._git_delivery is None:
            raise RuntimeError("local Git delivery was not composed")
        definition, state, changeset = self._rollback_inputs(
            owner_id, task_id, changeset_id,
        )
        if state.stage not in {
            EngineeringLoopStage.APPLIED,
            EngineeringLoopStage.COMMITTED,
            EngineeringLoopStage.ROLLED_BACK,
        }:
            raise PermissionError("rollback checkpoint requires applied state")
        if not self._git_delivery.has_committed_delivery(
            definition, changeset,
        ):
            return self._git_delivery.precommit_rollback_preview(
                definition, changeset,
            )
        return self._git_delivery.rollback_preview(definition, changeset)

    def rollback_candidate(
        self, owner_id: str, task_id: str, changeset_id: str, decision, *,
        session_id: str, principal_id: str, expected_head_object_id: str,
        message: str,
    ):
        self._require_owner(owner_id)
        if self._git_delivery is None:
            raise RuntimeError("local Git delivery was not composed")
        definition, state, record = self._rollback_inputs(
            owner_id, task_id, changeset_id,
        )
        committed_path = self._git_delivery.has_committed_delivery(
            definition, record,
        )
        if not committed_path:
            self._git_delivery.require_precommit_rollback_head(
                definition, record, expected_head_object_id,
            )
        rolled_back = self._candidates.rollback(
            owner_id, task_id, changeset_id, decision,
            expected_head_object_id,
            session_id=session_id, principal_id=principal_id,
        )
        if rolled_back.status.value != "explicitly_rolled_back":
            return rolled_back, None
        delivery = None
        if committed_path:
            delivery = self._git_delivery.rollback(
                definition, rolled_back, session_id=session_id,
                principal_id=principal_id, message=message,
            )
        if state.stage in {
            EngineeringLoopStage.APPLIED, EngineeringLoopStage.COMMITTED,
        }:
            self.lifecycle.record_rollback(
                task_id, rolled_back.rollback_receipt,
                None if delivery is None else delivery.commit_action,
                None if delivery is None else delivery.commit_receipt,
            )
        elif committed_path and (
            delivery.commit_receipt.receipt_id not in state.rollback_receipt_ids
            and not any(
                delivery.commit_receipt.receipt_id in receipt_id
                for receipt_id in state.rollback_receipt_ids
            )
        ):
            raise RuntimeError("local Git rollback lifecycle reconciliation conflicts")
        return rolled_back, delivery

    def remaining_budget(self, owner_id: str, task_id: str) -> dict[str, int]:
        self._require_owner(owner_id)
        state = self._store.load(task_id)
        if state is None:
            raise KeyError("engineering task is unavailable")
        budget = state.budget
        names = (
            "tokens", "wall_seconds", "commands", "network_bytes", "files",
            "storage_bytes",
        )
        return {
            name: getattr(budget, f"maximum_{name}") - getattr(budget, f"used_{name}")
            for name in names
        }

    def publish_candidate(
        self, owner_id: str, approval: GitPublicationApproval,
    ):
        return self._publication.publish_approval(owner_id, approval)

    def prepare_publication(
        self, owner_id: str, task_id: str, changeset_id: str, *,
        remote_name: str, credential_ref: str, title: str, body: str,
    ):
        return self._publication.prepare(
            owner_id, task_id, changeset_id, remote_name=remote_name,
            credential_ref=credential_ref, title=title, body=body,
        )

    def publication_for_task(self, owner_id: str, task_id: str):
        return self._publication.for_task(owner_id, task_id)

    def publication_status(self, owner_id: str, proposal_id: str) -> str | None:
        return self._publication.status(owner_id, proposal_id)

    def publication_receipt(self, owner_id: str, proposal_id: str):
        return self._publication.receipt(owner_id, proposal_id)

    def decline_publication_proposal(self, owner_id: str, proposal_id: str):
        return self._publication.decline(owner_id, proposal_id)

    def publication_grant_matches(self, owner_id: str, grant) -> bool:
        return self._publication.grant_matches(owner_id, grant)

    def approve_publication_proposal(
        self, owner_id: str, proposal_id: str,
    ):
        return self._publication.approve(owner_id, proposal_id)

    def record_generation_budget(
        self, owner_id: str, task_id: str, generation,
    ) -> None:
        self._require_owner(owner_id)
        state = self._store.load(task_id)
        if state is None:
            raise KeyError("engineering task is unavailable")
        self._validate_lifecycle_grant(
            task_id, state.grant_id, datetime.now(timezone.utc),
        )
        self._loop.record_auxiliary_evidence(
            task_id, "generation", generation.generation_id,
            instant=generation.updated_at,
            budget_delta={
                "used_tokens": generation.consumed_tokens,
                "used_wall_seconds": generation.consumed_wall_seconds,
            },
        )

    def record_failed_candidate_verifications(
        self, owner_id: str, task_id: str, records,
    ) -> None:
        self._require_owner(owner_id)
        values = tuple(records)
        if (
            not values
            or not any(not item.passed for item in values)
            or any(
            item.task_id != task_id
            or item.status.value not in {"completed", "recovery_required"}
            for item in values
            )
        ):
            raise ValueError("failed verification accounting requires failures")
        state = self._store.load(task_id)
        if state is None:
            raise KeyError("engineering task is unavailable")
        self._validate_lifecycle_grant(
            task_id, state.grant_id, datetime.now(timezone.utc),
        )
        for item in values:
            self._loop.record_auxiliary_evidence(
                task_id, "verification_failure", item.verification_id,
                instant=item.updated_at,
                budget_delta={"used_commands": 1},
            )

    def record_incident(
        self, owner_id: str, task_id: str, failure_code: str, evidence_ids,
    ):
        return self._incidents.record_failure(
            owner_id, task_id, failure_code, evidence_ids,
        )

    def incidents_for_task(self, owner_id: str, task_id: str):
        return self._incidents.for_task(owner_id, task_id)

    def incident_evidence_for_task(self, owner_id: str, task_id: str):
        return self._incidents.receipts_for_task(owner_id, task_id)

    def inspect_incident(self, owner_id: str, incident_id: str):
        return self._incidents.inspect(owner_id, incident_id)

    def advance_incident(self, owner_id, incident_id, stage, evidence_id):
        return self._incidents.advance(
            owner_id, incident_id, stage, evidence_id,
        )

    def record_incident_evidence(
        self, owner_id, incident_id, kind, source_evidence_ids, conclusion_code,
    ):
        return self._incidents.record_evidence(
            owner_id, incident_id, kind, source_evidence_ids, conclusion_code,
        )

    def record_trusted_review(self, owner_id, checkpoint):
        return self._reviews.record_trusted(owner_id, checkpoint)

    def record_review_selection(self, owner_id, selection):
        return self._reviews.record_selection(owner_id, selection)

    def record_trusted_review_resolution(self, owner_id, receipt):
        return self._reviews.record_trusted_resolution(owner_id, receipt)

    def waive_review_finding(self, owner_id, decision):
        return self._reviews.waive(owner_id, decision)

    def reviews_for_task(self, owner_id: str, task_id: str):
        return self._reviews.for_task(owner_id, task_id)

    def review_evidence_for_task(self, owner_id: str, task_id: str):
        return self._reviews.evidence_for_task(owner_id, task_id)

    def record_generated_documentation(self, owner_id, request, receipt):
        return self._documentation.record_generated(owner_id, request, receipt)

    def record_documentation_selection(self, owner_id, selection):
        return self._documentation.record_selection(owner_id, selection)

    def begin_documentation_generation(self, owner_id, request):
        return self._documentation.begin_generation(owner_id, request)

    def record_requirement_trace(self, owner_id, trace):
        verifications = self._candidates.verifications(owner_id, trace.task_id)
        trusted = tuple(
            item.evidence.evidence_id for item in verifications
            if item.passed and item.evidence is not None
        )
        return self._documentation.record_trace(
            owner_id, trace, trusted_evidence_ids=trusted,
        )

    def documentation_for_task(self, owner_id: str, task_id: str):
        return self._documentation.for_task(owner_id, task_id)

    def runtime_diagnostics_requested(self, owner_id: str, task_id: str) -> bool:
        return self._runtime_diagnostics.requested(owner_id, task_id)

    def run_runtime_diagnostics(
        self, owner_id: str, task_id: str, *, session_id: str,
        principal_id: str, preferred_paths=(), postapply: bool = False,
    ):
        requests, receipts = self._runtime_diagnostics.execute_selected(
            owner_id, task_id, session_id=session_id,
            principal_id=principal_id, preferred_paths=preferred_paths,
            postapply=postapply,
        )
        for receipt in receipts:
            self._record_runtime_diagnostic_budget(task_id, receipt)
        return requests, receipts

    def capture_runtime_performance_baseline(
        self, owner_id: str, task_id: str, *, session_id: str,
        principal_id: str, preferred_paths=(),
    ):
        requests, receipts = (
            self._runtime_diagnostics.capture_performance_baseline(
                owner_id, task_id, session_id=session_id,
                principal_id=principal_id, preferred_paths=preferred_paths,
            )
        )
        for receipt in receipts:
            self._record_runtime_diagnostic_budget(task_id, receipt)
        return requests, receipts

    def runtime_diagnostic_requests(self, owner_id: str, task_id: str):
        return self._runtime_diagnostics.requests_for_task(owner_id, task_id)

    def runtime_diagnostic_receipts(self, owner_id: str, task_id: str):
        return self._runtime_diagnostics.receipts_for_task(owner_id, task_id)

    def database_engineering_requested(
        self, owner_id: str, task_id: str,
    ) -> bool:
        return self._databases.requested(owner_id, task_id)

    def run_database_engineering(
        self, owner_id: str, task_id: str, changed_paths, changeset_id: str, *,
        session_id: str, principal_id: str,
    ):
        return self._databases.execute_natural(
            owner_id, task_id, changed_paths, changeset_id,
            session_id=session_id, principal_id=principal_id,
        )

    def database_plans(self, owner_id: str, task_id: str):
        return self._databases.plans_for_task(owner_id, task_id)

    def database_results(self, owner_id: str, task_id: str):
        return self._databases.results_for_task(owner_id, task_id)

    def reverify_database(
        self, owner_id: str, task_id: str, *, record_lifecycle: bool = True,
    ):
        return self._databases.reverify_postapply(
            owner_id, task_id, record_lifecycle=record_lifecycle,
        )

    def accept_database_postapply(
        self, owner_id: str, task_id: str, receipts,
    ) -> None:
        self._databases.accept_postapply(owner_id, task_id, receipts)

    def database_postapply_receipts(self, owner_id: str, task_id: str):
        return self._databases.postapply_for_task(owner_id, task_id)

    def record_integration_environment(
        self, owner_id, task_id, plan, start_result, cleanup_receipt, *,
        postapply: bool,
    ) -> None:
        self._require_owner(owner_id)
        state = self._store.load(task_id)
        if state is None:
            raise KeyError("engineering task is unavailable")
        if (
            plan.task_id != task_id
            or plan.approved_changeset_id == ""
            or start_result.environment_id != plan.environment_id
            or start_result.plan_sha256 != integration_environment_plan_digest(plan)
            or start_result.permit.approved_changeset_id
            != plan.approved_changeset_id
            or start_result.receipt.status is not IntegrationEnvironmentStatus.READY
            or cleanup_receipt.status is not IntegrationEnvironmentStatus.CLEANED
            or cleanup_receipt.environment_id != plan.environment_id
            or cleanup_receipt.permit_id != start_result.permit.permit_id
            or cleanup_receipt.services != start_result.receipt.services
            or not cleanup_receipt.cleanup_evidence_ids
            or (not postapply and plan.candidate_id != state.candidate_id)
        ):
            raise ValueError("integration environment evidence is not exact and complete")
        elapsed = max(0, int(
            (cleanup_receipt.completed_at - start_result.receipt.started_at)
            .total_seconds()
        ))
        self._loop.record_integration_environment(
            task_id, cleanup_receipt.receipt_id,
            instant=cleanup_receipt.completed_at, postapply=postapply,
            budget_delta={
                "used_commands": 2,
                "used_wall_seconds": min(elapsed, plan.resource_impact.max_wall_seconds),
                "used_network_bytes": (
                    0 if cleanup_receipt.network_usage is None else
                    cleanup_receipt.network_usage.transmitted_bytes
                    + cleanup_receipt.network_usage.received_bytes
                ),
            },
        )

    def fresh_owner_candidate(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        preparation = self.preparation(owner_id, task_id)
        state = self._store.load(task_id)
        if state is None or state.stage not in {
            EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED,
        }:
            raise PermissionError("post-apply integration requires applied state")
        return CandidateWorkspaceAdapter(
            Path(preparation.candidate.owner_workspace), self._candidate_root,
        ).create(task_id)

    def select_verification_recipes(self, owner_id: str, task_id: str):
        """Select trusted installed recipes; callers cannot propose coordinates."""
        self._require_owner(owner_id)
        definition = self._store.load_task(task_id)
        if definition is None:
            raise KeyError("engineering task definition is unavailable")
        if not definition.task.toolchains and any(
            item.verification.status.value == "verified"
            for item in self._databases.results_for_task(owner_id, task_id)
        ):
            return ()
        if self._recipe_catalog is None:
            raise RuntimeError("installed engineering recipes are unavailable")
        priorities = (
            ToolRecipePurpose.TEST, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS,
            ToolRecipePurpose.BUILD,
        )
        selected = []
        for toolchain in definition.task.toolchains:
            matches = self._recipe_catalog.matching(toolchain, priorities)
            if not matches:
                raise LookupError(
                    f"no installed signed verification recipe for {toolchain}"
                )
            selected.append((toolchain, matches[0]))
        if not selected and not any(
            item.verification.status.value == "verified"
            for item in self._databases.results_for_task(owner_id, task_id)
        ) and not natural_integration_environment_requested(definition.task.intent):
            raise LookupError("engineering task has no verification toolchains")
        return tuple(selected)

    def close(self) -> None:
        self._databases.close()
        self._runtime_diagnostics.close()
        self._documentation.close()
        self._reviews.close()
        self._incidents.close()
        self._publication.close()
        if self._git_delivery is not None:
            self._git_delivery.close()
        self._candidates.close()
        self._preparations.close()
        self._store.close()

    def _require_owner(self, owner_id: str) -> None:
        if owner_id != self.owner_id:
            raise PermissionError("engineering task owner is invalid")

    def _record_runtime_diagnostic_budget(self, task_id, receipt) -> None:
        elapsed = max(
            0, int((receipt.completed_at - receipt.started_at).total_seconds())
        )
        self._loop.record_auxiliary_evidence(
            task_id, "runtime_diagnostic", receipt.receipt_id,
            instant=receipt.completed_at,
            budget_delta={"used_commands": 1, "used_wall_seconds": elapsed},
        )

    def _accept_verifications(
        self, task_id, records, *, additional_budget=None, postapply,
    ) -> None:
        values = tuple(records)
        if not values or any(
            item.task_id != task_id
            or item.status.value != "completed"
            or not item.passed
            for item in values
        ):
            raise ValueError("engineering verification set is not wholly successful")
        for index, record in enumerate(values):
            if postapply:
                self.lifecycle.record_reverification(record.evidence)
            else:
                self.lifecycle.record_verification(
                    record.evidence,
                    additional_budget=additional_budget if index == 0 else None,
                )

    def _rollback_inputs(self, owner_id, task_id, changeset_id):
        definition = self._store.load_task(task_id)
        state = self._store.load(task_id)
        changesets = tuple(
            item for item in self._candidates.changesets(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if definition is None or state is None or len(changesets) != 1:
            raise KeyError("local rollback inputs are unavailable")
        self._validate_lifecycle_grant(
            task_id, definition.task.grant_id, datetime.now(timezone.utc),
        )
        return definition, state, changesets[0]

    def _validate_lifecycle_grant(
        self, task_id: str, grant_id: str, instant: datetime,
    ) -> None:
        grant = self._grants.usable(grant_id)
        definition = self._store.load_task(task_id)
        if (
            grant is None
            or definition is None
            or grant.owner_id != self.owner_id
            or not grant.active_at(instant)
            or grant.scope.kind is not EngineeringGrantScopeKind.TASK
            or grant.scope.scope_id != task_id
        ):
            raise PermissionError("engineering task grant is unavailable")
        _validate_task_grant(definition.task, grant, instant)

    def _validate_publication_approval(self, approval) -> None:
        self._publication.validate_approval(approval)

def _view(value, definition) -> dict:
    if definition is None:
        raise RuntimeError("engineering task definition is unavailable")
    return {
        "task_id": value.task_id,
        "stage": value.stage,
        "revision": value.revision,
        "task_graph_evidence_id": value.task_graph_evidence_id,
        "candidate_id": value.candidate_id,
        "diff_checkpoint_id": value.diff_checkpoint_id,
        "test_receipt_ids": list(value.test_receipt_ids),
        "runtime_diagnostic_receipt_ids": list(
            value.runtime_diagnostic_receipt_ids
        ),
        "database_receipt_ids": list(value.database_receipt_ids),
        "database_postapply_receipt_ids": list(
            value.database_postapply_receipt_ids
        ),
        "integration_environment_receipt_ids": list(
            value.integration_environment_receipt_ids
        ),
        "integration_environment_postapply_receipt_ids": list(
            value.integration_environment_postapply_receipt_ids
        ),
        "dependency_receipt_ids": list(value.dependency_receipt_ids),
        "design_preview_receipt_ids": list(value.design_preview_receipt_ids),
        "rollback_receipt_ids": list(value.rollback_receipt_ids),
        "git_receipt_ids": list(value.git_receipt_ids),
        "publication_approval_id": value.publication_approval_id,
        "budget": value.budget,
        "intent": definition.task.intent,
        "workspace_roots": list(definition.task.workspace_roots),
        "acceptance_policy_id": definition.acceptance_policy_id,
    }


def _validate_task_grant(task, grant, instant) -> None:
    scope = grant.scope
    if (
        scope.kind is not EngineeringGrantScopeKind.TASK
        or scope.scope_id != task.task_id
        or task.grant_id != grant.grant_id
        or not set(task.workspace_roots).issubset(scope.workspace_roots)
        or not set(task.authorities).issubset(grant.authorities)
        or not set(task.toolchains).issubset(scope.toolchains)
        or not set(task.network_hosts).issubset(scope.network_hosts)
        or not set(task.package_registries).issubset(scope.package_registries)
        or (task.git_remote is not None and task.git_remote not in scope.git_remotes)
        or (task.git_branch is not None and task.git_branch not in scope.git_branches)
        or task.max_wall_seconds > grant.resource_impact.max_wall_seconds
        or task.max_tool_runs > grant.resource_impact.max_tool_runs
        or task.max_changed_files > grant.resource_impact.max_changed_files
        or task.max_changed_bytes > grant.resource_impact.max_changed_bytes
        or not (task.created_at <= instant < task.expires_at)
    ):
        raise PermissionError("engineering task exceeds the exact grant scope")
