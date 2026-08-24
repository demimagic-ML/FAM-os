"""Compile bounded immutable production plans from policy-owned intent."""

from fam_os.core.contracts import (
    ExecutionPlan,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    StepOutcome,
    TerminalDisposition,
)
from fam_os.core.production.contracts import ModelIntent
from fam_os.routing import RouteDecision


class ProductionPlanCompiler:
    def compile(
        self,
        request_id: str,
        route: RouteDecision,
        intent: ModelIntent,
        verification_required: bool,
        acceptance_id: str | None = None,
    ) -> ExecutionPlan:
        if verification_required:
            steps, transitions = _verified_graph(route, intent, acceptance_id)
        else:
            steps, transitions = _unverified_graph(route, intent)
        return ExecutionPlan(
            f"plan-{request_id}", request_id, route, "inference", steps,
            transitions, verification_required,
        )


def _inference(route: RouteDecision, intent: ModelIntent) -> PlanStep:
    return PlanStep(
        "inference", PlanStepKind.INFERENCE,
        f"Generate a {intent.value.replace('_', ' ')} candidate",
        route.required_capabilities,
    )


def _terminals() -> tuple[PlanStep, PlanStep, PlanStep]:
    return (
        PlanStep("release", PlanStepKind.FINALIZE, "Release accepted result", terminal_disposition=TerminalDisposition.RELEASE),
        PlanStep("withhold", PlanStepKind.FINALIZE, "Withhold unsafe result", terminal_disposition=TerminalDisposition.WITHHOLD),
        PlanStep("fail", PlanStepKind.FINALIZE, "Fail safely", terminal_disposition=TerminalDisposition.FAIL),
    )


def _unverified_graph(route, intent):
    release, withhold, fail = _terminals()
    steps = (_inference(route, intent), release, withhold, fail)
    transitions = (
        PlanTransition("inference", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("inference", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("inference", StepOutcome.FAILED, "fail"),
    )
    return steps, transitions


def _verified_graph(route, intent, acceptance_id=None):
    acceptance = acceptance_id or f"acceptance.{intent.value}"
    release, withhold, fail = _terminals()
    primary_verify = PlanStep(
        "verify-primary", PlanStepKind.VERIFY, "Verify economical candidate",
        acceptance_ids=(acceptance,),
    )
    repair = PlanStep(
        "inference-repair", PlanStepKind.INFERENCE,
        "Repair using exact verifier feedback", route.required_capabilities,
    )
    repair_verify = PlanStep(
        "verify-repair", PlanStepKind.VERIFY, "Verify repaired candidate",
        acceptance_ids=(acceptance,),
    )
    escalation = PlanStep(
        "inference-escalation", PlanStepKind.INFERENCE,
        "Generate a strong escalation candidate", route.required_capabilities,
    )
    escalation_verify = PlanStep(
        "verify-escalation", PlanStepKind.VERIFY, "Verify strong candidate",
        acceptance_ids=(acceptance,),
    )
    fallback = PlanStep(
        "inference-escalation-fallback", PlanStepKind.INFERENCE,
        "Generate an independent strong fallback candidate", route.required_capabilities,
    )
    fallback_verify = PlanStep(
        "verify-escalation-fallback", PlanStepKind.VERIFY,
        "Verify independent strong fallback",
        acceptance_ids=(acceptance,),
    )
    steps = (
        _inference(route, intent), primary_verify, repair, repair_verify, escalation,
        escalation_verify, fallback, fallback_verify, release, withhold, fail,
    )
    transitions = (
        PlanTransition("inference", StepOutcome.SUCCEEDED, "verify-primary"),
        PlanTransition("inference", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("inference", StepOutcome.FAILED, "fail"),
        PlanTransition("verify-primary", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("verify-primary", StepOutcome.FAILED, "inference-repair"),
        PlanTransition("verify-primary", StepOutcome.UNAVAILABLE, "withhold"),
        PlanTransition("verify-primary", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("inference-repair", StepOutcome.SUCCEEDED, "verify-repair"),
        PlanTransition("inference-repair", StepOutcome.FAILED, "fail"),
        PlanTransition("inference-repair", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("verify-repair", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("verify-repair", StepOutcome.FAILED, "inference-escalation"),
        PlanTransition("verify-repair", StepOutcome.UNAVAILABLE, "withhold"),
        PlanTransition("verify-repair", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("inference-escalation", StepOutcome.SUCCEEDED, "verify-escalation"),
        PlanTransition("inference-escalation", StepOutcome.FAILED, "inference-escalation-fallback"),
        PlanTransition("inference-escalation", StepOutcome.UNAVAILABLE, "withhold"),
        PlanTransition("inference-escalation", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("verify-escalation", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("verify-escalation", StepOutcome.FAILED, "inference-escalation-fallback"),
        PlanTransition("verify-escalation", StepOutcome.UNAVAILABLE, "withhold"),
        PlanTransition("verify-escalation", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("inference-escalation-fallback", StepOutcome.SUCCEEDED, "verify-escalation-fallback"),
        PlanTransition("inference-escalation-fallback", StepOutcome.FAILED, "fail"),
        PlanTransition("inference-escalation-fallback", StepOutcome.CANCELLED, "withhold"),
        PlanTransition("verify-escalation-fallback", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("verify-escalation-fallback", StepOutcome.FAILED, "withhold"),
        PlanTransition("verify-escalation-fallback", StepOutcome.UNAVAILABLE, "withhold"),
        PlanTransition("verify-escalation-fallback", StepOutcome.CANCELLED, "withhold"),
    )
    return steps, transitions
