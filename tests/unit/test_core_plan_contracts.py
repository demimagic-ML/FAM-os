import unittest

from fam_os.core.contracts import (
    CORE_CONTRACT_VERSION,
    ExecutionPlan,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    StepOutcome,
    TerminalDisposition,
)
from fam_os.routing import RouteDecision, RouteName


class ExecutionPlanTests(unittest.TestCase):
    def test_represents_bounded_verified_code_flow(self) -> None:
        plan = _verified_code_plan()
        self.assertEqual(plan.contract_version, CORE_CONTRACT_VERSION)
        self.assertEqual(plan.entry_step_id, "economical-inference")
        self.assertEqual(
            {step.terminal_disposition for step in plan.steps if step.terminal_disposition},
            {TerminalDisposition.RELEASE, TerminalDisposition.WITHHOLD},
        )

    def test_rejects_uncovered_routed_capability(self) -> None:
        with self.assertRaisesRegex(ValueError, "cover"):
            ExecutionPlan(
                "plan-1",
                "request-1",
                RouteDecision(RouteName.CODE, 1.0, "code task", ("retrieval",)),
                "inference",
                (
                    _inference("inference"),
                    _verify("verify"),
                    _terminal("release", TerminalDisposition.RELEASE),
                ),
                (
                    PlanTransition("inference", StepOutcome.SUCCEEDED, "verify"),
                    PlanTransition("verify", StepOutcome.SUCCEEDED, "release"),
                ),
            )

    def test_rejects_release_without_accepted_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "accepted evidence"):
            ExecutionPlan(
                "plan-1",
                "request-1",
                RouteDecision(RouteName.CODE, 1.0, "code task", ("code",)),
                "inference",
                (
                    _inference("inference"),
                    _terminal("release", TerminalDisposition.RELEASE),
                ),
                (PlanTransition("inference", StepOutcome.SUCCEEDED, "release"),),
                verification_required=True,
            )

    def test_rejects_release_only_plan(self) -> None:
        with self.assertRaisesRegex(ValueError, "inbound transition"):
            ExecutionPlan(
                "plan-1",
                "request-1",
                RouteDecision(RouteName.KERNEL, 1.0, "direct response"),
                "release",
                (_terminal("release", TerminalDisposition.RELEASE),),
                (),
            )

    def test_allows_non_verified_release_after_normal_work(self) -> None:
        plan = ExecutionPlan(
            "plan-1",
            "request-1",
            RouteDecision(RouteName.KERNEL, 1.0, "direct response", ("language",)),
            "inference",
            (
                PlanStep(
                    "inference",
                    PlanStepKind.INFERENCE,
                    "Generate conversational response",
                    capability_ids=("language",),
                ),
                _terminal("release", TerminalDisposition.RELEASE),
            ),
            (PlanTransition("inference", StepOutcome.SUCCEEDED, "release"),),
        )
        self.assertFalse(plan.verification_required)

    def test_rejects_transition_cycle(self) -> None:
        with self.assertRaisesRegex(ValueError, "cycles"):
            ExecutionPlan(
                "plan-1",
                "request-1",
                RouteDecision(RouteName.CODE, 1.0, "code task", ("code",)),
                "inference",
                (
                    _inference("inference"),
                    _verify("verify"),
                    _terminal("release", TerminalDisposition.RELEASE),
                ),
                (
                    PlanTransition("inference", StepOutcome.SUCCEEDED, "verify"),
                    PlanTransition("verify", StepOutcome.SUCCEEDED, "release"),
                    PlanTransition("verify", StepOutcome.FAILED, "inference"),
                ),
            )

    def test_rejects_unreachable_step(self) -> None:
        with self.assertRaisesRegex(ValueError, "reachable"):
            ExecutionPlan(
                "plan-1",
                "request-1",
                RouteDecision(RouteName.CODE, 1.0, "code task", ("code",)),
                "inference",
                (
                    _inference("inference"),
                    _verify("verify"),
                    _terminal("release", TerminalDisposition.RELEASE),
                    _terminal("orphan", TerminalDisposition.FAIL),
                ),
                (
                    PlanTransition("inference", StepOutcome.SUCCEEDED, "verify"),
                    PlanTransition("verify", StepOutcome.SUCCEEDED, "release"),
                ),
            )


def _verified_code_plan() -> ExecutionPlan:
    steps = (
        _inference("economical-inference"),
        _verify("economical-verification"),
        _inference("repair-inference"),
        _verify("repair-verification"),
        _inference("escalation-inference"),
        _verify("escalation-verification"),
        _terminal("release", TerminalDisposition.RELEASE),
        _terminal("withhold", TerminalDisposition.WITHHOLD),
    )
    transitions = (
        PlanTransition(
            "economical-inference", StepOutcome.SUCCEEDED, "economical-verification"
        ),
        PlanTransition("economical-inference", StepOutcome.FAILED, "withhold"),
        PlanTransition("economical-verification", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("economical-verification", StepOutcome.FAILED, "repair-inference"),
        PlanTransition("repair-inference", StepOutcome.SUCCEEDED, "repair-verification"),
        PlanTransition("repair-inference", StepOutcome.FAILED, "escalation-inference"),
        PlanTransition("repair-verification", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("repair-verification", StepOutcome.FAILED, "escalation-inference"),
        PlanTransition(
            "escalation-inference", StepOutcome.SUCCEEDED, "escalation-verification"
        ),
        PlanTransition("escalation-inference", StepOutcome.FAILED, "withhold"),
        PlanTransition("escalation-verification", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("escalation-verification", StepOutcome.FAILED, "withhold"),
    )
    return ExecutionPlan(
        "verified-code-plan-1",
        "request-1",
        RouteDecision(RouteName.CODE, 1.0, "verified code task", ("code",)),
        "economical-inference",
        steps,
        transitions,
        verification_required=True,
    )


def _inference(step_id: str) -> PlanStep:
    return PlanStep(
        step_id,
        PlanStepKind.INFERENCE,
        f"Run {step_id}",
        capability_ids=("code",),
    )


def _verify(step_id: str) -> PlanStep:
    return PlanStep(
        step_id,
        PlanStepKind.VERIFY,
        f"Run {step_id}",
        acceptance_ids=("python.tests",),
    )


def _terminal(step_id: str, disposition: TerminalDisposition) -> PlanStep:
    return PlanStep(
        step_id,
        PlanStepKind.FINALIZE,
        f"Finalize with {disposition.value}",
        terminal_disposition=disposition,
    )


if __name__ == "__main__":
    unittest.main()
