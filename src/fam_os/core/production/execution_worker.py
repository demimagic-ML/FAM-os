"""Background candidate generation over durable Core task state."""

import logging

from datetime import UTC, datetime
from typing import ContextManager, Protocol

from fam_os.core.contracts import StepOutcome
from fam_os.core.lifecycle import (
    CandidateEvidenceRecord,
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.ports.inference import InferenceRequest
from fam_os.core.production.contracts import (
    InferenceExecutionRecord,
    InferenceExecutionState,
    ModelIntent,
)
from fam_os.core.production.execution_state import replace_execution, terminal_execution
from fam_os.core.production.generation_input import (
    PreparedGenerationInput,
    RemoteInferenceExecutor,
)
from fam_os.core.production.memory_port import SessionMemoryPort
from fam_os.core.production.adaptation_port import LiveAdaptationPort
from fam_os.core.production.attempt_budget import production_attempt_budget
from fam_os.core.production.action_candidate_retry import ActionCandidateRetry
from fam_os.core.production.verification_flow import VerificationFlow
from fam_os.core.production.remote_evidence import authenticated_remote_evidence
from fam_os.core.production.remote_recovery import (
    RemoteAttemptRecoveryCoordinator,
    accepted_remote_contract_sha256,
    classify_remote_failure,
    remote_attempt_reservation,
)
from fam_os.core.production.retrieval_fallback import (
    normalize_local_retrieval_candidate,
)
from fam_os.fabric import (
    RemoteAttemptFailure,
    RemoteRecoveryDisposition,
)
from fam_os.verification.generation import generation_context
from fam_os.verification.declarations import RetrievalCitationsVerification


LOGGER = logging.getLogger(__name__)


class ModelLoader(Protocol):
    def ensure_model(self, model_ref: str) -> None: ...


class ModelResidencyPort(Protocol):
    def resident_models(self) -> tuple[str, ...]: ...

    def session(
        self, request_id: str, model_ref: str,
        context_tokens: int, maximum_output_tokens: int,
    ) -> ContextManager[None]: ...


class TaskExecutionWorker:
    def __init__(
        self, runtime, repositories, selector, capacity, budget_ledger_factory,
        verifier, model_loader: ModelLoader | None = None,
        memory: SessionMemoryPort | None = None,
        adaptation: LiveAdaptationPort | None = None,
        remote_executor: RemoteInferenceExecutor | None = None,
        failure_observer=None, residency: ModelResidencyPort | None = None,
    ) -> None:
        self._runtime = runtime
        self._repositories = repositories
        self._loader = model_loader
        self._memory = memory
        self._adaptation = adaptation
        self._remote_executor = remote_executor
        self._residency = residency
        self._budget_factory = budget_ledger_factory
        self._action_candidate_retry = ActionCandidateRetry(
            repositories, selector, capacity, self.resident_models,
            budget_ledger_factory,
        )
        self._recovery = RemoteAttemptRecoveryCoordinator(
            repositories, selector, capacity, self.resident_models,
            budget_ledger_factory,
        )
        self._verification = VerificationFlow(
            repositories, selector, capacity, self.resident_models,
            budget_ledger_factory, verifier, failure_observer,
        )

    def bind_remote_executor(self, executor: RemoteInferenceExecutor) -> None:
        if self._remote_executor is not None:
            raise RuntimeError("remote inference executor is already bound")
        self._remote_executor = executor

    def run(self, instance_id: str) -> None:
        while True:
            record = self._require_record(instance_id)
            snapshot = self._require_plan(instance_id)
            if snapshot.terminal:
                return
            if record.state in {
                InferenceExecutionState.PREPARED,
                InferenceExecutionState.RUNNING,
            }:
                record = self.generate_candidate(record)
                snapshot = self._require_plan(instance_id)
            if snapshot.terminal:
                return
            if record.state is InferenceExecutionState.CANDIDATE_READY:
                snapshot, _ = self._verification.accept_or_withhold(snapshot, record)
            if snapshot.terminal:
                return

    def resident_models(self) -> tuple[str, ...]:
        try:
            if self._residency is not None:
                return self._residency.resident_models()
            return tuple(item.model_ref for item in self._runtime.loaded_models())
        except Exception:
            return ()

    def generate_candidate(
        self, record: InferenceExecutionRecord, grounded_context: str = "",
        maximum_output_token_limit: int | None = None,
    ) -> InferenceExecutionRecord:
        running = replace_execution(
            self._repositories, record, state=InferenceExecutionState.RUNNING,
        )
        try:
            reconciled = self._recovery.reconcile_completed(running)
            if reconciled is not None:
                return reconciled
            request = self._repositories.requests.get(running.request_id)
            if request is None:
                raise RuntimeError("durable request is missing")
            request_prompt = request.prompt
            prompt = request_prompt
            memory_context = (
                "" if self._memory is None
                else self._memory.context_for_request(request.request_id)
            )
            declaration = self._repositories.verifications.declaration_for_request(
                request.request_id,
            )
            verification = generation_context(declaration)
            if verification.prompt_suffix:
                prompt += "\n\n" + verification.prompt_suffix
            if running.verifier_feedback:
                prompt += "\n\nDeterministic verifier feedback:\n" + running.verifier_feedback
            snapshot = self._require_plan(running.instance_id)
            recovery = self._repositories.final_evidence.remote_recovery_for_request(
                running.request_id,
            )
            remote = running.remote_plan is not None and not running.remote_attempt_consumed
            if (
                running.remote_plan is not None
                and running.remote_attempt_consumed
                and recovery is None
                and self._repositories.final_evidence.remote_execution_for_request(
                    running.request_id,
                ) is None
            ):
                return self._recovery.reconcile_interrupted(running, snapshot)
            local_recovery = (
                recovery is not None
                and recovery.disposition
                is RemoteRecoveryDisposition.LOCAL_RETRY_PENDING
            )
            if local_recovery and (
                running.selection.selection_id != recovery.local_selection_id
            ):
                running = self._recovery.restore_local_selection(running, recovery)
            context_tokens = (
                min(32768, max(1, running.remote_plan.maximum_context_bytes // 4))
                if remote else 32768
            )
            local_output_tokens = (
                8192 if running.intent is ModelIntent.APPLICATION_MUTATION else 1024
            )
            maximum_output_tokens = (
                min(
                    local_output_tokens,
                    max(1, running.remote_plan.descriptor.maximum_output_bytes // 4),
                )
                if remote else local_output_tokens
            )
            if maximum_output_token_limit is not None:
                maximum_output_tokens = min(
                    maximum_output_tokens, maximum_output_token_limit,
                )
            preliminary = PreparedGenerationInput(
                prompt, memory_context, grounded_context,
                verification.images, context_tokens, maximum_output_tokens,
                (
                    verification.json_output
                    or running.intent is ModelIntent.APPLICATION_MUTATION
                ),
                0.0 if running.intent is ModelIntent.APPLICATION_MUTATION else 0.2,
            )
            messages = preliminary.messages(running.intent)
            if self._adaptation is not None and not remote:
                context_tokens = self._adaptation.context_tokens(
                    running.request_id, running.intent, running.selection.model_ref,
                    messages, maximum_output_tokens, context_tokens,
                )
            if context_tokens < 2:
                raise RuntimeError("inference context cannot reserve output tokens")
            maximum_output_tokens = min(
                maximum_output_tokens, max(1, context_tokens // 2),
            )
            prepared = PreparedGenerationInput(
                prompt, memory_context, grounded_context, verification.images,
                context_tokens, maximum_output_tokens,
                (
                    verification.json_output
                    or running.intent is ModelIntent.APPLICATION_MUTATION
                ),
                0.0 if running.intent is ModelIntent.APPLICATION_MUTATION else 0.2,
            )
            if remote:
                if self._remote_executor is None:
                    raise RuntimeError("remote inference executor is unavailable")
                acceptance_sha256 = accepted_remote_contract_sha256(
                    self._repositories, running, snapshot,
                )
                reservation = remote_attempt_reservation(
                    running, acceptance_sha256, prepared.maximum_output_tokens,
                )
                ledger = self._budget_factory(
                    production_attempt_budget(running.instance_id),
                )
                existing = ledger.reservation(reservation.reservation_id)
                if existing is not None:
                    running = replace_execution(
                        self._repositories, running, remote_attempt_consumed=True,
                    )
                    return self._recovery.prepare_local_retry(
                        running, snapshot, RemoteAttemptFailure.UNCERTAIN_COMPLETION,
                        existing,
                    )
                if ledger.reserve(reservation) is None:
                    raise RuntimeError("remote inference budget is exhausted")
                running = replace_execution(
                    self._repositories, running, remote_attempt_consumed=True,
                )
                try:
                    exchange = self._remote_executor.execute(running, prepared)
                except Exception as error:
                    return self._recovery.prepare_local_retry(
                        running, snapshot, classify_remote_failure(error), reservation,
                    )
                response = exchange.response
            else:
                inference_request = InferenceRequest(
                    running.selection.model_ref, prepared.messages(running.intent),
                    prepared.context_tokens, prepared.maximum_output_tokens,
                    json_output=prepared.json_output,
                    temperature=prepared.temperature,
                )
                if self._residency is None:
                    if self._loader is not None:
                        self._loader.ensure_model(running.selection.model_ref)
                    response = self._runtime.chat(inference_request)
                else:
                    with self._residency.session(
                        running.request_id, running.selection.model_ref,
                        prepared.context_tokens, prepared.maximum_output_tokens,
                    ):
                        response = self._runtime.chat(inference_request)
                self._notify_adaptation(running, response)
            candidate_content = response.content
            if (
                not remote
                and declaration is not None
                and isinstance(
                    declaration.specification, RetrievalCitationsVerification,
                )
            ):
                candidate_content = normalize_local_retrieval_candidate(
                    candidate_content, request_prompt, declaration.specification,
                )
            candidate_id = f"candidate-{running.request_id}-{running.revision + 1}"
            candidate = CandidateEvidenceRecord(
                candidate_id, running.request_id, f"plan-{running.request_id}",
                candidate_content,
            )
            recorded = (
                self._repositories.final_evidence.add_remote_candidate(
                    candidate,
                    authenticated_remote_evidence(
                        running, exchange, reservation, candidate,
                    ),
                )
                if remote else
                self._repositories.final_evidence.add_recovered_candidate(
                    candidate, datetime.now(UTC),
                )
                if local_recovery else
                self._repositories.final_evidence.add_candidate(candidate)
            )
            if not recorded:
                raise RuntimeError("candidate evidence already exists")
            return replace_execution(
                self._repositories, running,
                state=InferenceExecutionState.CANDIDATE_READY,
                candidate_id=candidate_id,
                remote_attempt_consumed=(running.remote_attempt_consumed or remote),
            )
        except Exception:
            LOGGER.exception(
                "candidate generation failed for request %s",
                running.request_id,
            )
            self._recovery.fail_pending(running.request_id)
            return self._generation_failed(record, running)

    def retry_action_candidate(
        self, record: InferenceExecutionRecord, grounded_context: str,
        feedback: str, *, escalation: bool,
    ) -> InferenceExecutionRecord | None:
        preparation = self._action_candidate_retry.prepare(
            record, feedback, escalation=escalation,
        )
        if preparation is None:
            return None
        return self.generate_candidate(
            preparation.record, grounded_context,
            preparation.maximum_output_tokens,
        )

    def _notify_adaptation(self, running, response) -> None:
        if self._adaptation is None:
            return
        try:
            self._adaptation.inference_completed(
                running.instance_id, running.request_id, running.intent,
                running.selection.model_ref, response.metrics,
            )
        except Exception:
            LOGGER.exception(
                "live adaptation telemetry failed for request %s",
                running.request_id,
            )

    def _generation_failed(self, original, running):
        snapshot = self._require_plan(original.instance_id)
        if snapshot.current_step_id == "inference-escalation":
            return self._verification.fallback_after_provider_failure(snapshot, running)
        recovery = self._repositories.final_evidence.remote_recovery_for_request(
            running.request_id,
        )
        references = (
            () if recovery is None else
            (PlanEvidenceReference(
                recovery.evidence_id, PlanEvidenceKind.REMOTE_RECOVERY, None,
            ),)
        )
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.FAILED, references,
        )
        if advanced.rejection is not None:
            raise RuntimeError("failed inference could not terminate")
        return terminal_execution(
            self._repositories, running, failure_code="expert.generation.failed",
        )

    def _require_record(self, instance_id):
        record = self._repositories.inference_executions.get(instance_id)
        if record is None:
            raise KeyError("task session does not exist")
        return record

    def _require_plan(self, instance_id):
        snapshot = self._repositories.plans.get(instance_id)
        if snapshot is None:
            raise KeyError("task plan does not exist")
        return snapshot
