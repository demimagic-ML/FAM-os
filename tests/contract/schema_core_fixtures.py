"""Representative Core, routing, failure, and degradation schema values."""

from fam_os.core.contracts import (
    DegradationDisposition,
    DegradationImpact,
    DegradationKind,
    DegradationNotice,
    ExecutionPlan,
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    ResultStatus,
    RetryDisposition,
    StepOutcome,
    TaskRequest,
    TaskResult,
    TerminalDisposition,
)
from fam_os.routing import RouteDecision, RouteName, RoutingRequest, RoutingResult
from fam_os.telemetry.contracts import InferenceMetrics


def route() -> RouteDecision:
    return RouteDecision(RouteName.KERNEL, 0.9, "Kernel route", ("chat.respond",))


def task_request() -> TaskRequest:
    return TaskRequest("request-1", "Help with this task", ("chat.respond",))


def execution_plan() -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="plan-1",
        request_id="request-1",
        route=route(),
        entry_step_id="answer",
        steps=(
            PlanStep("answer", PlanStepKind.INFERENCE, "Generate answer", ("chat.respond",)),
            PlanStep(
                "release",
                PlanStepKind.FINALIZE,
                "Release answer",
                terminal_disposition=TerminalDisposition.RELEASE,
            ),
        ),
        transitions=(PlanTransition("answer", StepOutcome.SUCCEEDED, "release"),),
    )


def failure() -> FailureEnvelope:
    return FailureEnvelope(
        error_id="error-1",
        category=FailureCategory.PROVIDER_FAILURE,
        code="inference.provider_failed",
        safe_message="The inference provider did not complete the request.",
        component=FailureComponent.EXPERT,
        retry=RetryDisposition.WITH_BACKOFF,
        capability_id="chat.respond",
        evidence_ids=("evidence-1",),
    )


def degradation() -> DegradationNotice:
    return DegradationNotice(
        degradation_id="degradation-1",
        kind=DegradationKind.FALLBACK_USED,
        code="routing.fallback_used",
        safe_message="A lower-cost response capability was used.",
        component=FailureComponent.ROUTING,
        impact=DegradationImpact.LOW,
        disposition=DegradationDisposition.CONTINUE,
        original_capability_id="chat.large",
        replacement_capability_id="chat.respond",
        evidence_ids=("evidence-2",),
    )


def task_result() -> TaskResult:
    item = failure()
    return TaskResult(
        request_id="request-1",
        status=ResultStatus.FAILED,
        content=None,
        reason=item.safe_message,
        plan_id="plan-1",
        evidence_ids=item.evidence_ids,
        failure=item,
    )


def routing_request() -> RoutingRequest:
    return RoutingRequest("request-1", "Help with this task", ("chat.respond",))


def routing_result() -> RoutingResult:
    return RoutingResult(
        route(),
        InferenceMetrics("router", 0.2, 0.1, 12, 3, 15.0),
    )


def core_schema_values() -> tuple[object, ...]:
    return (
        task_request(),
        execution_plan(),
        task_result(),
        routing_request(),
        routing_result(),
        failure(),
        degradation(),
    )
