"""Bounded route, generate, verify, repair, escalate, and release use case."""

from __future__ import annotations

from dataclasses import dataclass, field

from fam_os.core.contracts.request import TaskRequest
from fam_os.core.contracts.result import ResultStatus, TaskResult
from fam_os.core.execution.attempt import AttemptExecutor, CandidateGenerationError
from fam_os.core.execution.contracts import (
    AttemptKind,
    ExecutionAttempt,
    ExecutionStatus,
    VerifiedExecutionOutcome,
)
from fam_os.core.execution.placement import PlacementExecutionError, PlacementExecutor
from fam_os.core.execution.policy import VerifiedCodePolicy
from fam_os.core.execution.prompts import expert_messages, repair_messages
from fam_os.core.execution.errors import ExecutionConfigurationError
from fam_os.core.execution.terminal_results import (
    execution_failed_result,
    unsupported_route_result,
    verification_failed_result,
)
from fam_os.core.ports.inference import InferenceMessage
from fam_os.experts.contracts import ExpertDescriptor
from fam_os.experts.ports import ExpertCatalog
from fam_os.routing.contracts import RouteName, RoutingRequest, RoutingResult
from fam_os.routing.ports import TaskRouter
from fam_os.scheduler.contracts import PlacementPlan
from fam_os.verification.contracts import VerificationStatus


@dataclass(slots=True)
class _RunState:
    request: TaskRequest
    policy: VerifiedCodePolicy
    routing: RoutingResult
    attempts: list[ExecutionAttempt] = field(default_factory=list)
    evicted_expert_ids: list[str] = field(default_factory=list)

    @property
    def last_attempt(self) -> ExecutionAttempt:
        if not self.attempts:
            raise RuntimeError("execution has no attempts")
        return self.attempts[-1]

    def record_evictions(self, expert_ids: tuple[str, ...]) -> None:
        for expert_id in expert_ids:
            if expert_id not in self.evicted_expert_ids:
                self.evicted_expert_ids.append(expert_id)


class VerifiedCodeExecution:
    def __init__(
        self,
        router: TaskRouter,
        catalog: ExpertCatalog,
        placement: PlacementExecutor,
        attempts: AttemptExecutor,
    ) -> None:
        self._router = router
        self._catalog = catalog
        self._placement = placement
        self._attempts = attempts

    def execute(
        self,
        request: TaskRequest,
        policy: VerifiedCodePolicy,
    ) -> VerifiedExecutionOutcome:
        routing = self._router.route(self._routing_request(request))
        state = _RunState(request, policy, routing)
        if routing.decision.route is not RouteName.CODE:
            return self._route_not_supported(state)
        try:
            self._run_economical(state)
            terminal = self._terminal_after_attempt(state)
            if terminal:
                return terminal
            if not policy.escalate_on_failure:
                return self._verification_failed(state)
            self._run_escalation(state)
            return self._terminal_after_attempt(state) or self._verification_failed(state)
        except (CandidateGenerationError, ExecutionConfigurationError, PlacementExecutionError) as exc:
            return self._error(state, exc)

    @staticmethod
    def _routing_request(request: TaskRequest) -> RoutingRequest:
        return RoutingRequest(
            request_id=request.request_id,
            prompt=request.prompt,
            required_capabilities=request.required_capabilities,
        )

    def _run_economical(self, state: _RunState) -> None:
        expert, placement = self._prepare(state, state.policy.economical_expert_id)
        self._execute_attempt(
            state,
            AttemptKind.ECONOMICAL,
            expert,
            placement,
            expert_messages(state.request.prompt),
        )
        self._run_repairs(state, expert, placement, state.policy.repair_attempts, AttemptKind.REPAIR)

    def _run_escalation(self, state: _RunState) -> None:
        expert_id = state.policy.escalation_expert_id or ""
        expert, placement = self._prepare(state, expert_id)
        self._execute_repair(state, AttemptKind.ESCALATION, expert, placement)
        self._run_repairs(
            state,
            expert,
            placement,
            state.policy.escalation_repair_attempts,
            AttemptKind.ESCALATION_REPAIR,
        )

    def _run_repairs(
        self,
        state: _RunState,
        expert: ExpertDescriptor,
        placement: PlacementPlan,
        limit: int,
        kind: AttemptKind,
    ) -> None:
        for _ in range(limit):
            if state.last_attempt.verification.passed:
                return
            if state.last_attempt.verification.status is VerificationStatus.ERROR:
                return
            self._execute_repair(state, kind, expert, placement)

    def _execute_repair(
        self,
        state: _RunState,
        kind: AttemptKind,
        expert: ExpertDescriptor,
        placement: PlacementPlan,
    ) -> None:
        previous = state.last_attempt
        messages = repair_messages(
            state.request.prompt,
            previous.candidate,
            previous.verification,
            state.policy.repair_guidance,
            state.policy.repair_context,
        )
        self._execute_attempt(state, kind, expert, placement, messages)

    def _execute_attempt(
        self,
        state: _RunState,
        kind: AttemptKind,
        expert: ExpertDescriptor,
        placement: PlacementPlan,
        messages: tuple[InferenceMessage, ...],
    ) -> None:
        attempt_id = f"{state.request.request_id}:{len(state.attempts) + 1}"
        attempt = self._attempts.execute(
            attempt_id,
            kind,
            expert,
            placement,
            messages,
            state.policy.generation,
        )
        state.attempts.append(attempt)

    def _prepare(
        self,
        state: _RunState,
        expert_id: str,
    ) -> tuple[ExpertDescriptor, PlacementPlan]:
        expert = self._catalog.get(expert_id)
        if expert is None:
            raise ExecutionConfigurationError(f"unknown expert: {expert_id}")
        prepared = self._placement.prepare(expert)
        state.record_evictions(prepared.evicted_expert_ids)
        return expert, prepared.plan

    def _terminal_after_attempt(
        self,
        state: _RunState,
    ) -> VerifiedExecutionOutcome | None:
        report = state.last_attempt.verification
        if report.status is VerificationStatus.ERROR:
            return self._error(state, report.reason)
        if not report.passed:
            return None
        statuses = {
            AttemptKind.ECONOMICAL: ExecutionStatus.VERIFIED,
            AttemptKind.REPAIR: ExecutionStatus.VERIFIED_AFTER_REPAIR,
            AttemptKind.ESCALATION: ExecutionStatus.VERIFIED_AFTER_ESCALATION,
            AttemptKind.ESCALATION_REPAIR: ExecutionStatus.VERIFIED_AFTER_ESCALATION_REPAIR,
        }
        return self._verified(state, statuses[state.last_attempt.kind])

    @staticmethod
    def _verified(state: _RunState, status: ExecutionStatus) -> VerifiedExecutionOutcome:
        attempt = state.last_attempt
        result = TaskResult(
            request_id=state.request.request_id,
            status=ResultStatus.VERIFIED,
            content=attempt.candidate,
            verified=True,
            reason=attempt.verification.reason,
            evidence_ids=(attempt.verification.verification_id,),
        )
        return VerifiedCodeExecution._outcome(state, status, result)

    @staticmethod
    def _verification_failed(state: _RunState) -> VerifiedExecutionOutcome:
        evidence_id = state.last_attempt.verification.verification_id
        result = verification_failed_result(state.request.request_id, evidence_id)
        return VerifiedCodeExecution._outcome(state, ExecutionStatus.VERIFICATION_FAILED, result)

    @staticmethod
    def _route_not_supported(state: _RunState) -> VerifiedExecutionOutcome:
        route = state.routing.decision.route.value
        result = unsupported_route_result(state.request.request_id, route)
        return VerifiedCodeExecution._outcome(state, ExecutionStatus.ROUTE_NOT_SUPPORTED, result)

    @staticmethod
    def _error(state: _RunState, error: RuntimeError) -> VerifiedExecutionOutcome:
        result = execution_failed_result(state.request.request_id, error)
        return VerifiedCodeExecution._outcome(state, ExecutionStatus.ERROR, result)

    @staticmethod
    def _outcome(
        state: _RunState,
        status: ExecutionStatus,
        result: TaskResult,
    ) -> VerifiedExecutionOutcome:
        return VerifiedExecutionOutcome(
            request_id=state.request.request_id,
            status=status,
            routing=state.routing,
            result=result,
            attempts=tuple(state.attempts),
            evicted_expert_ids=tuple(state.evicted_expert_ids),
        )
