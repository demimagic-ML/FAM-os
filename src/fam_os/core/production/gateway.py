"""Durable installed Shell gateway over the real Core lifecycle."""

from __future__ import annotations

import logging
from typing import Callable

from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.ingress.shell_views import project_shell_snapshot
from fam_os.core.lifecycle import (
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.lifecycle.global_budget import GlobalAttemptBudget
from fam_os.core.production.contracts import InferenceExecutionState
from fam_os.core.production.attempt_budget import production_attempt_budget
from fam_os.core.production.application_gateway import ApplicationShellGateway
from fam_os.core.production.action_ingress_router import ActionIngressRouter
from fam_os.core.production.application_worker import ApplicationTaskWorker
from fam_os.core.production.execution_state import terminal_execution
from fam_os.core.production.execution_worker import ModelLoader, TaskExecutionWorker
from fam_os.core.production.inference_starter import InferenceRequestStarter
from fam_os.core.production.intent import DeterministicIntentClassifier
from fam_os.core.production.grounding_port import (
    GroundedRequestPreparer,
    GroundingAccessContext,
)
from fam_os.core.production.model_selection import HostCapacity, ResourceAwareModelSelector
from fam_os.core.production.memory_port import SessionMemoryPort
from fam_os.core.production.plan_compiler import ProductionPlanCompiler
from fam_os.core.production.terminal_projection import TerminalResultProjector
from fam_os.core.production.terminal_reconciliation import (
    reconcile_terminal_execution,
)
from fam_os.core.production.verification import (
    DeclaredTextVerifier,
    DeclaredVerifier,
    exact_text_declaration,
)
from fam_os.core.production.worker_registry import TaskWorkerRegistry
from fam_os.shell import ShellCancelCommand, ShellDecisionCommand
from fam_os.schemas import loads_document
from fam_os.verification import VerificationDeclaration


_LOGGER = logging.getLogger(__name__)


class ProductionTaskGateway:
    """Run natural requests through admission, routing, plan, and final policy."""

    def __init__(
        self,
        runtime,
        repositories,
        selector: ResourceAwareModelSelector,
        capacity: Callable[[], HostCapacity],
        budget_ledger_factory: Callable[[GlobalAttemptBudget], object],
        model_loader: ModelLoader | None = None,
        classifier: DeterministicIntentClassifier | None = None,
        verifier: DeclaredVerifier | None = None,
        applications=None,
        memory: SessionMemoryPort | None = None,
        grounding=None,
        outcomes=None,
        adaptation=None,
        remote_planner=None,
        remote_executor=None,
        failure_observer=None,
        residency=None,
    ) -> None:
        self._repositories = repositories
        self._selector = selector
        self._capacity = capacity
        self._budget_factory = budget_ledger_factory
        self._classifier = classifier or DeterministicIntentClassifier()
        self._action_ingress = ActionIngressRouter(applications)
        self._memory = memory
        self._outcomes_enabled = outcomes is not None
        self._grounding = GroundedRequestPreparer(grounding)
        self._terminal = TerminalResultProjector(repositories, memory, outcomes)
        self._compiler = ProductionPlanCompiler()
        self._execution = TaskExecutionWorker(
            runtime, repositories, selector, capacity, budget_ledger_factory,
            verifier or DeclaredTextVerifier(), model_loader, memory, adaptation,
            remote_executor, failure_observer, residency,
        )
        self._starter = InferenceRequestStarter(
            repositories, selector, capacity, self._execution.resident_models,
            self._compiler, self._budget,
            remote_planner,
        )
        self._applications = applications
        self._application_execution = (
            None if applications is None else
            ApplicationTaskWorker(repositories, applications, self._execution)
        )
        self._application_gateway = (
            None if applications is None else ApplicationShellGateway(
                repositories, applications, self._classifier, selector, capacity,
                self._execution, self._budget,
            )
        )
        self.reversals = (
            None if self._application_gateway is None
            else self._application_gateway.reversals
        )
        self._workers = TaskWorkerRegistry()

    def bind_remote_planner(self, planner) -> None:
        self._starter.bind_remote_planner(planner)

    def bind_remote_executor(self, executor) -> None:
        self._execution.bind_remote_executor(executor)

    def ask(self, command):
        session_id = command.memory_session_id or f"shell-{command.request_id}"
        # Remote authority is an explicit routing boundary, not an application
        # intent hint. Validate its fabric binding before any ingress fallback
        # can convert the request into a withheld local result.
        if command.remote_authority is not None:
            intent = self._classifier.classify(command.prompt, ())
            return self._start_inference(
                command, intent, "local-owner", session_id, None,
            )
        routed = self._action_ingress.route(command, session_id)
        if routed.terminal_result is not None:
            return routed.terminal_result
        command = routed.command
        context_capabilities = tuple(
            capability for context in command.contexts
            for capability in context.capability_ids
        )
        intent = self._classifier.classify(
            command.prompt,
            tuple(dict.fromkeys((*command.required_capabilities, *context_capabilities))),
        )
        if command.contexts or command.required_capabilities:
            if self._application_gateway is None:
                return self._action_ingress.unavailable(
                    command.request_id,
                    "Application Fabric is unavailable; no action was attempted.",
                )
            accepted = self._application_gateway.ask(
                command, intent, routed.deterministic_parameters,
            )
            self._remember_request(command, "local-owner", command.memory_session_id)
            return accepted
        command, declaration = self._grounding.prepare(
            command, intent, GroundingAccessContext("fam.shell", session_id),
        )
        if declaration is None and command.verification_required:
            declaration = exact_text_declaration(command.request_id, command.prompt)
        return self._start_inference(
            command, intent, "local-owner", session_id, declaration,
        )

    def ask_verified(self, verified):
        command = verified.command
        if command.contexts or command.required_capabilities:
            raise ValueError("declared verifier tasks cannot acquire application authority")
        blocked = self._action_ingress.block_delegated(
            command,
            command.memory_session_id or f"shell-{command.request_id}",
        )
        if blocked is not None:
            return blocked
        declaration = loads_document(verified.declaration_document)
        if not isinstance(declaration, VerificationDeclaration):
            raise ValueError("verified ask requires a verification declaration")
        if declaration.request_id != command.request_id:
            raise ValueError("verified ask request identities must match")
        intent = self._classifier.classify(command.prompt, ())
        return self._start_inference(
            command, intent, "local-owner",
            command.memory_session_id or f"shell-{command.request_id}",
            declaration,
        )

    def ask_as(self, command, principal_id: str, session_id: str):
        """Submit a non-application task for an already authenticated client."""
        if command.contexts or command.required_capabilities:
            raise ValueError("delegated tasks cannot acquire application authority")
        blocked = self._action_ingress.block_delegated(command, session_id)
        if blocked is not None:
            return blocked
        intent = self._classifier.classify(command.prompt, ())
        command, declaration = self._grounding.prepare(
            command, intent, GroundingAccessContext("fam.mcp", session_id),
        )
        if declaration is None and command.verification_required:
            declaration = exact_text_declaration(command.request_id, command.prompt)
        return self._start_inference(
            command, intent, principal_id, session_id, declaration,
        )

    def verification_runs(self, session_id: str):
        record, _snapshot = self._state(session_id)
        return self._repositories.verifications.runs_for_request(record.request_id)

    def remote_execution_evidence(self, session_id: str):
        record, _snapshot = self._state(session_id)
        return self._repositories.final_evidence.remote_execution_for_request(
            record.request_id,
        )

    def remote_recovery_evidence(self, session_id: str):
        record, _snapshot = self._state(session_id)
        return self._repositories.final_evidence.remote_recovery_for_request(
            record.request_id,
        )

    def attempt_budget_evidence(self, session_id: str):
        record, _snapshot = self._state(session_id)
        ledger = self._budget(record.instance_id)
        snapshot = ledger.snapshot()
        reservations = tuple(
            reservation
            for reservation_id in snapshot.reservation_ids
            if (reservation := ledger.reservation(reservation_id)) is not None
        )
        if len(reservations) != len(snapshot.reservation_ids):
            raise RuntimeError("attempt budget evidence is incomplete")
        return snapshot, reservations

    def application_activity(self, session_id: str):
        self._state(session_id)
        return self._repositories.application_executions.get(session_id)

    def _start_inference(
        self, command, intent, principal_id, session_id, declaration=None,
    ):
        accepted = self._starter.start(
            command, intent, principal_id, session_id, declaration,
        )
        self._remember_request(command, principal_id, session_id)
        return accepted

    def snapshot(self, session_id: str):
        record, snapshot = self._state(session_id)
        if self._application_gateway is not None:
            blocked = self._application_gateway.blocking_view(session_id, snapshot)
            if blocked is not None:
                return blocked
        if snapshot.terminal:
            if record.state is not InferenceExecutionState.TERMINAL:
                self._ensure_worker(session_id)
            self._workers.wait(session_id)
            record, snapshot = self._state(session_id)
            if record.state is not InferenceExecutionState.TERMINAL:
                self._terminalize_worker_failure(session_id)
                record, snapshot = self._state(session_id)
        if snapshot.terminal and record.state is InferenceExecutionState.TERMINAL:
            return self._terminal_view(record, snapshot)
        if not snapshot.terminal:
            self._ensure_worker(session_id)
            record, snapshot = self._state(session_id)
        if snapshot.terminal and record.state is InferenceExecutionState.TERMINAL:
            self._workers.wait(session_id)
            record, snapshot = self._state(session_id)
            return self._terminal_view(record, snapshot)
        message = _progress_message(record, snapshot)
        return project_shell_snapshot(
            session_id, snapshot, snapshot.revision + 1, message=message,
        )

    def decide(self, command: ShellDecisionCommand):
        if self._application_gateway is None:
            raise ValueError("Application Fabric is unavailable")
        snapshot, record = self._application_gateway.decide(command)
        if record is not None:
            return self._terminal_view(record, snapshot)
        self._ensure_worker(command.session_id)
        return project_shell_snapshot(
            command.session_id, snapshot, snapshot.revision + 1,
            message="Approved action is executing with postcondition verification.",
        )

    def cancel(self, command: ShellCancelCommand):
        record, snapshot = self._state(command.session_id)
        if self._repositories.application_executions.get(command.session_id) is not None:
            if self._application_gateway is None:
                raise RuntimeError("Application Fabric is unavailable")
            cancelled, terminal = self._application_gateway.cancel(command, snapshot)
            return self._terminal_view(terminal, cancelled)
        if command.expected_revision not in {0, snapshot.revision + 1}:
            raise ValueError("task cancellation revision is stale")
        reference = PlanEvidenceReference(
            f"cancel-{record.request_id}-{snapshot.revision}",
            PlanEvidenceKind.CANCELLATION, None,
        )
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision,
            StepOutcome.CANCELLED, (reference,),
        )
        if advanced.rejection is not None:
            raise ValueError("task cannot be cancelled in its current state")
        terminal = terminal_execution(
            self._repositories, record, failure_code="core.request.cancelled",
        )
        return self._terminal_view(terminal, advanced.snapshot)

    def _ensure_worker(self, instance_id: str) -> None:
        self._workers.start(instance_id, self._run_worker)

    def _run_worker(self, instance_id: str) -> None:
        try:
            if self._repositories.application_executions.get(instance_id) is not None:
                if self._application_execution is None:
                    raise RuntimeError("Application Fabric worker is unavailable")
                self._application_execution.run(instance_id)
            else:
                self._execution.run(instance_id)
        except Exception:
            _LOGGER.exception("task worker failed for %s", instance_id)
            self._terminalize_worker_failure(instance_id)
        if self._outcomes_enabled:
            record, snapshot = self._state(instance_id)
            if snapshot.terminal and record.state is InferenceExecutionState.TERMINAL:
                self._terminal_view(record, snapshot)

    def _terminalize_worker_failure(self, instance_id: str) -> None:
        record = self._repositories.inference_executions.get(instance_id)
        snapshot = self._repositories.plans.get(instance_id)
        if record is None or snapshot is None:
            return
        if not snapshot.terminal:
            advanced = PlanLifecycleService(self._repositories.plans).advance(
                instance_id, snapshot.revision, StepOutcome.FAILED,
            )
            if advanced.rejection is not None:
                return
            snapshot = advanced.snapshot
        if record.state is not InferenceExecutionState.TERMINAL:
            reconcile_terminal_execution(
                self._repositories, record, snapshot,
                failure_code="core.worker.failed",
            )

    def _budget(self, instance_id):
        return self._budget_factory(production_attempt_budget(instance_id))

    def _terminal_view(self, record, snapshot):
        return self._terminal.project(record, snapshot)

    def _remember_request(self, command, principal_id, session_id) -> None:
        if self._memory is not None:
            self._memory.begin_request(
                command.request_id, principal_id,
                session_id or f"shell-{command.request_id}", command.prompt,
            )

    def _state(self, instance_id):
        record = self._repositories.inference_executions.get(instance_id)
        snapshot = self._repositories.plans.get(instance_id)
        if record is None or snapshot is None:
            raise KeyError("task session does not exist")
        return record, snapshot


def _progress_message(record, snapshot) -> str:
    if snapshot.terminal:
        return "Finalizing durable evidence"
    current = next(
        step for step in snapshot.plan.steps
        if step.step_id == snapshot.current_step_id
    )
    if current.kind is PlanStepKind.PREPARE_ACTION:
        return "Resolving a bounded action proposal from authorized evidence"
    return f"Running {record.selection.model_ref}"
