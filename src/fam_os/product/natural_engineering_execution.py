"""Product coordinator from prepared intent to a verified changeset checkpoint."""

from __future__ import annotations

import hashlib

from fam_os.core.ports.inference import TransientInferenceError

from fam_os.core.engineering import (
    CandidateChangesetStatus, CandidateEditStatus,
    CandidateGenerationService, CandidateGenerationStatus,
    CandidateVerificationStatus, bind_generated_candidate_plan,
    generated_candidate_plan_digest,
    RuntimeDiagnosticStatus,
    DatabaseChangeStatus,
    EngineeringAuthority,
    EngineeringReviewStatus,
)
from fam_os.schemas import encode_document
from fam_os.product.natural_engineering_repair import (
    NaturalEngineeringRepairCoordinator,
)
from fam_os.product.natural_engineering_trace import (
    NaturalEngineeringTraceCoordinator,
)
class NaturalEngineeringExecutionCoordinator:
    def __init__(
        self, loop, context_reader, generation: CandidateGenerationService,
        documentation=None, reviewer=None, integration=None, agent=None,
    ) -> None:
        self._loop = loop
        self._context_reader = context_reader
        self._generation = generation
        self._documentation = documentation
        self._reviewer = reviewer
        self._integration = integration
        self._agent = agent
        self._repair = NaturalEngineeringRepairCoordinator(
            loop, context_reader, generation,
        )
        self._trace = NaturalEngineeringTraceCoordinator(loop)

    def execute(
        self, owner_id: str, definition, *, session_id: str, principal_id: str,
        goal_mode: bool = False,
    ) -> dict:
        task = definition.task
        preparation = self._loop.preparation(owner_id, task.task_id)
        preferred = tuple(dict.fromkeys(
            preparation.analysis.relevant_paths
            + preparation.analysis.affected_test_paths
        ))
        context = self._context_reader.read(
            preparation.candidate, task.intent, preferred,
        )
        agent_evidence_ids: tuple[str, ...] = ()
        try:
            baseline_requests, baseline_receipts = (
                self._loop.capture_runtime_performance_baseline(
                    owner_id, task.task_id, session_id=session_id,
                    principal_id=principal_id, preferred_paths=preferred,
                )
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "runtime_diagnostic_failed",
                "performance_baseline_capture_unavailable", (),
            )
        if any(
            item.status is not RuntimeDiagnosticStatus.PASSED
            for item in baseline_receipts
        ):
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "runtime_diagnostic_failed", "performance_baseline_capture_failed",
                tuple(item.receipt_id for item in baseline_receipts),
            )
        budget = self._loop.remaining_budget(owner_id, task.task_id)
        record = None
        if self._agent is None:
            generation_id = f"generation-{task.task_id}-1"
            record = self._generation.generate(
                definition, preparation, context, generation_id=generation_id,
                session_id=session_id, principal_id=principal_id,
                available_tokens=budget["tokens"],
                available_wall_seconds=budget["wall_seconds"],
            )
            self._loop.record_generation_budget(owner_id, task.task_id, record)
            if record.status is not CandidateGenerationStatus.PLAN_VALIDATED:
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "generation_failed", record.failure_code,
                    (record.generation_id,),
                )
            producer_id = record.generation_id
            generation_summary = record.plan.summary
            generation_attempt_count = record.attempt_count
            generation_consumed_tokens = record.consumed_tokens
            changeset_seed = generated_candidate_plan_digest(record.plan)
            edits = bind_generated_candidate_plan(
                task.task_id, preparation.candidate, record.plan,
                maximum_operations=min(task.max_changed_files, budget["files"]),
                maximum_content_bytes=min(task.max_changed_bytes, budget["storage_bytes"]),
            )
            applied = self._apply_edits(
                owner_id, task.task_id, session_id, principal_id, edits,
            )
        else:
            try:
                agent_result = self._agent.execute(
                    owner_id, definition, preparation,
                    session_id=session_id, principal_id=principal_id,
                    maximum_steps=256 if goal_mode else None,
                )
            except TransientInferenceError:
                raise
            except (OSError, PermissionError, RuntimeError, ValueError) as error:
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "generation_failed", f"iterative_agent_failed:{type(error).__name__}",
                    (),
                )
            producer_id = agent_result.producer_id
            generation_summary = agent_result.summary
            generation_attempt_count = agent_result.agent_outcome.model_steps
            generation_consumed_tokens = 0
            applied = agent_result.applied_edits
            agent_verified = bool(agent_result.successful_verifications)
            changeset_seed = _applied_digest(applied)
        changeset_id = _changeset_identity(task.task_id, changeset_seed)
        if any(item.status is not CandidateEditStatus.APPLIED for item in applied):
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "candidate_edit_failed", "candidate_edit_postcondition_failed",
                tuple(item.edit_id for item in applied),
            )
        database = None
        if self._loop.database_engineering_requested(owner_id, task.task_id):
            try:
                database = self._loop.run_database_engineering(
                    owner_id, task.task_id,
                    tuple(item.operation.path for item in applied), changeset_id,
                    session_id=session_id, principal_id=principal_id,
                )
            except (LookupError, PermissionError, RuntimeError, ValueError):
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "database_engineering_failed",
                    "database_plan_or_compensation_unavailable", (),
                )
            if (
                database is None
                or database.verification.status
                is not DatabaseChangeStatus.VERIFIED
            ):
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "database_engineering_failed",
                    (
                        "database_execution_compensated"
                        if database is not None else
                        "database_verified_result_unavailable"
                    ),
                    (
                        () if database is None else
                        (database.verification.receipt_id,)
                    ),
                )
        documentation = ()
        if self._documentation is not None:
            try:
                documentation = self._documentation.generate(
                    owner_id, definition, session_id=session_id,
                    principal_id=principal_id,
                    preferred_paths=tuple(dict.fromkeys(
                        tuple(item.operation.path for item in applied)
                        + preparation.analysis.relevant_paths
                        + preparation.analysis.affected_test_paths
                    )),
                )
            except Exception:
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "documentation_failed",
                    "signed_documentation_generation_failed",
                    (producer_id,),
                )
        try:
            verifications = self._verify(
                owner_id, task.task_id, session_id, principal_id, producer_id,
            )
        except (LookupError, RuntimeError):
            if self._agent is None or not agent_verified:
                raise
            agent_evidence_ids = (self._loop.accept_agent_verification(
                owner_id, task.task_id, producer_id,
                tuple(item.operation.path for item in applied),
            ),)
            verifications = ()
        if any(
            item.status is not CandidateVerificationStatus.COMPLETED or not item.passed
            for item in verifications
        ):
            if database is not None:
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "verification_failed",
                    "database_candidate_verification_failed",
                    tuple(item.verification_id for item in verifications),
                )
            if self._agent is not None:
                feedback = _verification_feedback(verifications)
                try:
                    repair_agent = self._agent.execute(
                        owner_id, definition, preparation,
                        session_id=session_id, principal_id=principal_id,
                        objective=(
                            f"{task.intent}\n\nThe candidate verification failed. "
                            "Inspect the current candidate, diagnose the failure, fix it, "
                            f"and rerun the relevant checks.\n{feedback}"
                        ),
                        turn_suffix="repair-1",
                    )
                except (OSError, PermissionError, RuntimeError, ValueError):
                    return _failure(
                        self._loop, owner_id,
                        self._loop.inspect(owner_id, task.task_id),
                        "verification_failed", "iterative_agent_repair_failed",
                        tuple(item.verification_id for item in verifications),
                    )
                applied = (*applied, *repair_agent.applied_edits)
                producer_id = repair_agent.producer_id
                generation_summary = repair_agent.summary
                generation_attempt_count += repair_agent.agent_outcome.model_steps
                verifications = self._verify(
                    owner_id, task.task_id, session_id, principal_id, producer_id,
                )
                if any(
                    item.status is not CandidateVerificationStatus.COMPLETED
                    or not item.passed for item in verifications
                ):
                    return _failure(
                        self._loop, owner_id,
                        self._loop.inspect(owner_id, task.task_id),
                        "verification_failed", "iterative_agent_repair_exhausted",
                        tuple(item.verification_id for item in verifications),
                    )
                repaired_incident = None
            else:
                def regenerate(_record, repair_edits):
                    paths = tuple(dict.fromkeys(
                        tuple(item.operation.path for item in (*applied, *repair_edits))
                        + preparation.analysis.relevant_paths
                        + preparation.analysis.affected_test_paths
                    ))
                    return self._documentation.generate(
                        owner_id, definition, session_id=session_id,
                        principal_id=principal_id, preferred_paths=paths,
                    )

                repair = self._repair.attempt(
                    owner_id, definition, preparation, verifications, preferred,
                    session_id=session_id, principal_id=principal_id,
                    verify=self._verify,
                    before_verify=regenerate if documentation else None,
                )
                if not repair.passed:
                    return _known_failure(
                        self._loop, owner_id, task.task_id,
                        (
                            "documentation_failed"
                            if repair.failure_code
                            == "repair_documentation_regeneration_failed"
                            else "verification_failed"
                        ),
                        repair.failure_code,
                        repair.incident,
                    )
                record = repair.generation
                producer_id = record.generation_id
                generation_summary = record.plan.summary
                generation_attempt_count += record.attempt_count
                generation_consumed_tokens += record.consumed_tokens
                applied = (*applied, *repair.edits)
                verifications = repair.verifications
                if documentation:
                    documentation = repair.documentation
                repaired_incident = repair.incident
        else:
            repaired_incident = None
        diagnostic_paths = tuple(dict.fromkeys(
            tuple(item.operation.path for item in applied)
            + preparation.analysis.relevant_paths
            + preparation.analysis.affected_test_paths
        ))
        try:
            diagnostic_requests, diagnostics = self._loop.run_runtime_diagnostics(
                owner_id, task.task_id, session_id=session_id,
                principal_id=principal_id, preferred_paths=diagnostic_paths,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "runtime_diagnostic_failed",
                "signed_runtime_diagnostic_unavailable", (),
            )
        if any(item.status is not RuntimeDiagnosticStatus.PASSED for item in diagnostics):
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "runtime_diagnostic_failed",
                "signed_runtime_diagnostic_failed",
                tuple(item.receipt_id for item in diagnostics),
            )
        integration = None
        if (
            self._integration is not None
            and self._integration.requested(definition)
        ):
            try:
                integration = self._integration.run_candidate(
                    owner_id, definition, preparation.candidate,
                    tuple(item.operation.path for item in applied), changeset_id,
                    session_id=session_id, principal_id=principal_id,
                )
            except (LookupError, OSError, PermissionError, RuntimeError, ValueError):
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "integration_environment_failed",
                    "signed_integration_environment_failed", (),
                )
        traces = ()
        if documentation:
            traces = (self._trace.record(
                owner_id, definition, preparation, applied, verifications,
            ),)
        changeset = self._loop.preview_candidate(
            owner_id, task.task_id, changeset_id,
            verification_ids=tuple(
                item.verification_id for item in verifications
            ),
            runtime_diagnostic_receipt_ids=tuple(
                item.receipt_id for item in (*baseline_receipts, *diagnostics)
            ),
            database_receipt_ids=(
                () if database is None else
                (database.verification.receipt_id,)
            ),
            integration_environment_evidence=(
                () if integration is None else
                ((
                    integration.plan, integration.start_result,
                    integration.cleanup_receipt,
                ),)
            ),
            postgresql_evidence=(
                ()
                if integration is None
                or integration.postgresql_plan is None
                or integration.postgresql_verification is None
                else ((
                    integration.postgresql_plan,
                    integration.postgresql_verification,
                ),)
            ),
            agent_verification_evidence_ids=agent_evidence_ids,
        )
        if changeset.status is not CandidateChangesetStatus.PREVIEWED:
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "checkpoint_failed", "changeset_preview_unavailable",
                (changeset.changeset_id,),
            )
        selection = checkpoint = None
        if self._reviewer is not None:
            try:
                selection, checkpoint = self._reviewer.review(
                    owner_id, definition, changeset,
                    producer_id=producer_id,
                )
            except Exception:
                return _failure(
                    self._loop, owner_id,
                    self._loop.inspect(owner_id, task.task_id),
                    "review_failed", "signed_independent_review_failed",
                    (changeset.changeset_id,),
                )
        result = self._loop.inspect(owner_id, task.task_id)
        result.update({
            "outcome": (
                "independent_review_blocked"
                if checkpoint is not None
                and checkpoint.status is EngineeringReviewStatus.BLOCKED
                else "changeset_approval_required"
            ),
            "generation": {
                "generation_id": producer_id,
                "summary": generation_summary,
                "attempt_count": generation_attempt_count,
                "consumed_tokens": generation_consumed_tokens,
            },
            "candidate_edits": [encode_document(item) for item in applied],
            "generated_documentation": [
                encode_document(item) for item in documentation
            ],
            "requirement_traces": [encode_document(item) for item in traces],
            "candidate_verifications": [encode_document(item) for item in verifications],
            "runtime_diagnostic_requests": [
                encode_document(item)
                for item in (*baseline_requests, *diagnostic_requests)
            ],
            "runtime_diagnostics": [
                encode_document(item)
                for item in (*baseline_receipts, *diagnostics)
            ],
            "database_engineering": (
                None if database is None else _database_view(database)
            ),
            "integration_environment": (
                None if integration is None else _integration_view(integration)
            ),
            "changeset": encode_document(changeset),
        })
        if selection is not None:
            result["review_selection"] = encode_document(selection)
            result["review"] = encode_document(checkpoint)
        if repaired_incident is not None:
            result["incident"] = encode_document(repaired_incident)
            result["incident_evidence"] = [
                encode_document(item) for item in
                self._loop.incident_evidence_for_task(owner_id, task.task_id)
            ]
            result["repair_count"] = 1
        return result

    def answer(
        self, owner_id: str, definition, *, session_id: str,
    ) -> dict:
        if self._agent is None:
            raise LookupError("iterative engineering agent is unavailable")
        preparation = self._loop.preparation(
            owner_id, definition.task.task_id,
        )
        outcome = self._agent.answer(
            owner_id, definition, preparation, session_id=session_id,
        )
        result = self._loop.inspect(owner_id, definition.task.task_id)
        result.update({
            "outcome": "answer_ready",
            "answer": outcome.response.content,
            "agent_turn_id": outcome.turn_id,
            "tool_result_count": len(outcome.tool_results),
        })
        return result

    def thread(
        self, owner_id: str, session_id: str, workspace: str,
    ) -> dict[str, object]:
        if self._agent is None:
            raise LookupError("iterative engineering agent is unavailable")
        return self._agent.thread(owner_id, session_id, workspace)

    def control_thread(
        self, owner_id: str, session_id: str, workspace: str,
        kind: str, content: str,
    ) -> dict[str, object]:
        if self._agent is None:
            raise LookupError("iterative engineering agent is unavailable")
        return self._agent.control_thread(
            owner_id, session_id, workspace, kind, content,
        )

    def execute_diagnostics_only(
        self, owner_id: str, definition, *, session_id: str,
        principal_id: str,
    ) -> dict:
        task = definition.task
        preparation = self._loop.preparation(owner_id, task.task_id)
        preferred = tuple(dict.fromkeys(
            preparation.analysis.relevant_paths
            + preparation.analysis.affected_test_paths
        ))
        try:
            baseline_requests, baseline_receipts = (
                self._loop.capture_runtime_performance_baseline(
                    owner_id, task.task_id, session_id=session_id,
                    principal_id=principal_id, preferred_paths=preferred,
                )
            )
            requests, receipts = self._loop.run_runtime_diagnostics(
                owner_id, task.task_id, session_id=session_id,
                principal_id=principal_id, preferred_paths=preferred,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            return _failure(
                self._loop, owner_id,
                self._loop.inspect(owner_id, task.task_id),
                "runtime_diagnostic_failed",
                "signed_runtime_diagnostic_unavailable", (),
            )
        requests = (*baseline_requests, *requests)
        receipts = (*baseline_receipts, *receipts)
        passed = bool(receipts) and all(
            item.status is RuntimeDiagnosticStatus.PASSED for item in receipts
        )
        result = self._loop.inspect(owner_id, task.task_id)
        result.update({
            "outcome": (
                "runtime_diagnostics_completed" if passed
                else "runtime_diagnostic_failed"
            ),
            "runtime_diagnostic_requests": [
                encode_document(item) for item in requests
            ],
            "runtime_diagnostics": [encode_document(item) for item in receipts],
        })
        if not passed:
            result["failure_code"] = "signed_runtime_diagnostic_failed"
        return result

    def reverify_agent(self, owner_id: str, definition) -> str:
        if self._agent is None:
            raise LookupError("iterative engineering agent is unavailable")
        workspace = definition.task.workspace_roots[0]
        turn_id = self._agent.replay_verification(
            definition.task.task_id, workspace,
            full_os=(
                EngineeringAuthority.HOST_ADMIN in definition.task.authorities
            ),
        )
        return self._loop.accept_agent_reverification(
            owner_id, definition.task.task_id, turn_id,
            tuple(
                item.operation.path for item in self._loop.candidate_edits(
                    owner_id, definition.task.task_id,
                )
            ),
        )

    def reverify_diagnostics(
        self, owner_id: str, definition, *, session_id: str,
        principal_id: str,
    ):
        task_id = definition.task.task_id
        prior = tuple(
            item for item in self._loop.runtime_diagnostic_requests(
                owner_id, task_id,
            ) if item.phase.value == "candidate"
        )
        if not prior:
            return (), ()
        postapply = tuple(
            item for item in self._loop.runtime_diagnostic_requests(
                owner_id, task_id,
            ) if item.phase.value == "postapply"
        )
        if postapply:
            ids = {item.request_id for item in postapply}
            receipts = tuple(
                item for item in self._loop.runtime_diagnostic_receipts(
                    owner_id, task_id,
                ) if item.request_id in ids
            )
            if {item.request_id for item in receipts} != ids:
                raise RuntimeError("post-apply runtime diagnostic recovery is incomplete")
            return postapply, receipts
        preferred = tuple(item.target_argv[0] for item in prior)
        return self._loop.run_runtime_diagnostics(
            owner_id, task_id, session_id=session_id,
            principal_id=principal_id, preferred_paths=preferred,
            postapply=True,
        )

    def reverify_integration(
        self, owner_id: str, definition, changeset_id: str, *,
        session_id: str, principal_id: str,
    ):
        if (
            self._integration is None
            or not self._integration.requested(definition)
        ):
            return None
        return self._integration.run_postapply(
            owner_id, definition, changeset_id,
            session_id=session_id, principal_id=principal_id,
        )

    def integration_environments(self, owner_id: str, task_id: str):
        if self._integration is None:
            return ()
        return self._integration.for_task(owner_id, task_id)

    def close(self) -> None:
        self._generation.close()

    def _apply_edits(self, owner_id, task_id, session_id, principal_id, edits):
        values = []
        for item in edits:
            values.append(self._loop.edit_candidate(
                owner_id, task_id,
                edit_id=f"edit-{item.operation.operation_id}",
                session_id=session_id, principal_id=principal_id,
                operation=item.operation, artifact=item.artifact,
                content=item.content,
            ))
        return tuple(values)

    def _verify(self, owner_id, task_id, session_id, principal_id, generation):
        producer_id = (
            generation if isinstance(generation, str) else generation.generation_id
        )
        values = []
        selected = self._loop.select_verification_recipes(owner_id, task_id)
        if not selected:
            return ()
        for index, (toolchain, recipe) in enumerate(selected):
            values.append(self._loop.verify_candidate(
                owner_id, task_id,
                verification_id=f"verification-{producer_id}-{index}",
                session_id=session_id, principal_id=principal_id,
                toolchain=toolchain, recipe_id=recipe.recipe_id,
                recipe_version=recipe.recipe_version,
                record_lifecycle=False,
            ))
        if all(
            item.status is CandidateVerificationStatus.COMPLETED and item.passed
            for item in values
        ):
            self._loop.accept_candidate_verifications(
                owner_id, task_id, values,
            )
        else:
            self._loop.record_failed_candidate_verifications(
                owner_id, task_id, values,
            )
        return tuple(values)


def _failure(loop, owner_id, task, outcome, code, evidence_ids):
    task.update({"outcome": outcome, "failure_code": code})
    record = getattr(loop, "record_incident", None)
    if record is not None and evidence_ids:
        incident = record(
            owner_id, task["task_id"], code or outcome, evidence_ids,
        )
        if incident is not None:
            task["incident"] = encode_document(incident)
    return task


def _known_failure(loop, owner_id, task_id, outcome, code, incident):
    task = loop.inspect(owner_id, task_id)
    task.update({"outcome": outcome, "failure_code": code})
    if incident is not None:
        task["incident"] = encode_document(incident)
        task["incident_evidence"] = [
            encode_document(item)
            for item in loop.incident_evidence_for_task(owner_id, task_id)
        ]
    return task


def _changeset_identity(task_id: str, plan_sha256: str) -> str:
    digest = hashlib.sha256(f"{task_id}:{plan_sha256}".encode("utf-8")).hexdigest()
    return f"changeset-{digest[:32]}"


def _applied_digest(edits) -> str:
    payload = "\0".join(
        f"{item.operation.operation_id}:{item.operation.kind.value}:"
        f"{item.operation.path}:{item.after_sha256 or ''}"
        for item in edits
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verification_feedback(records) -> str:
    rows = []
    for item in records:
        evidence = getattr(item, "evidence", None)
        rows.append(
            f"- {item.verification_id}: passed={item.passed}; "
            f"failure={getattr(item, 'failure_code', None) or 'unspecified'}; "
            f"summary={getattr(evidence, 'summary', '') if evidence else ''}"
        )
    return "\n".join(rows)


def _database_view(result) -> dict:
    return {
        "plan": encode_document(result.plan),
        "backup": (
            None if result.backup is None else encode_document(result.backup)
        ),
        "verification": encode_document(result.verification),
        "backup_relative_path": result.backup_relative_path,
        "failure_code": result.failure_code,
    }


def _integration_view(result) -> dict:
    return {
        "plan": encode_document(result.plan),
        "start_result": encode_document(result.start_result),
        "cleanup_receipt": encode_document(result.cleanup_receipt),
        "postapply": result.postapply,
        "postgresql_plan": (
            None if result.postgresql_plan is None
            else encode_document(result.postgresql_plan)
        ),
        "postgresql_verification": (
            None if result.postgresql_verification is None
            else encode_document(result.postgresql_verification)
        ),
    }
