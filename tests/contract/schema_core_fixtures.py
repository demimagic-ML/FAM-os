"""Representative Core, routing, failure, and degradation schema values."""

import hashlib

from datetime import datetime, timedelta, timezone

from fam_os.core.admission.contracts import RequestAuthorityGrant
from fam_os.core.lifecycle.attempt_contracts import AttemptBudgetPolicy
from fam_os.core.lifecycle.contracts import (
    PlanAuthorityBinding,
    PlanEventKind,
    PlanInstanceSnapshot,
    PlanLifecycleEvent,
)
from fam_os.core.lifecycle.control_contracts import PlanDeadlinePolicy
from fam_os.core.lifecycle.final_contracts import (
    AcceptanceEvidenceRecord,
    CandidateEvidenceRecord,
)

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
    ResultCitation,
    ResultStatus,
    RetryDisposition,
    StepOutcome,
    TaskRequest,
    TaskResult,
    TaskResultV1Alpha1,
    TerminalDisposition,
)
from fam_os.routing import RouteDecision, RouteName, RoutingRequest, RoutingResult
from fam_os.telemetry.contracts import InferenceMetrics


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


def result_citation() -> ResultCitation:
    quote = "FAM_OS is local operating-system intelligence."
    return ResultCitation(
        "citation-1", "claim-1", quote, "source-1",
        "package://fam_os/product/FAM_OS_IDENTITY.md",
        "a" * 64, "package-resource-a", 0, len(quote), quote,
        hashlib.sha256(quote.encode("utf-8")).hexdigest(),
    )


def routing_request() -> RoutingRequest:
    return RoutingRequest("request-1", "Help with this task", ("chat.respond",))


def routing_result() -> RoutingResult:
    return RoutingResult(
        route(),
        InferenceMetrics("router", 0.2, 0.1, 12, 3, 15.0),
    )


def durable_core_values() -> tuple[object, ...]:
    plan = execution_plan()
    authority = RequestAuthorityGrant(
        "authority-1", "principal-1", "session-1", ("chat.respond",),
        NOW, NOW + timedelta(hours=1),
    )
    event = PlanLifecycleEvent(
        "event-1", 0, NOW, PlanEventKind.STARTED, plan.entry_step_id,
    )
    snapshot = PlanInstanceSnapshot(
        "instance-1", plan, plan.entry_step_id, 0, (event,),
        authority_binding=PlanAuthorityBinding(
            "admission-1", NOW + timedelta(hours=1),
        ),
    )
    return (
        authority,
        snapshot,
        AttemptBudgetPolicy(plan.plan_id, (), (), 0, 0),
        PlanDeadlinePolicy(plan.plan_id, NOW + timedelta(minutes=5)),
        CandidateEvidenceRecord("candidate-1", "request-1", plan.plan_id, "answer"),
        AcceptanceEvidenceRecord("acceptance-1", "candidate-1", ("check-1",), True),
        event,
    )


def core_schema_values() -> tuple[object, ...]:
    return (
        task_request(),
        execution_plan(),
        task_result(),
        TaskResultV1Alpha1(
            "legacy-request-1", ResultStatus.COMPLETED, "legacy answer",
        ),
        result_citation(),
        routing_request(),
        routing_result(),
        failure(),
        degradation(),
        *durable_core_values(),
    )
