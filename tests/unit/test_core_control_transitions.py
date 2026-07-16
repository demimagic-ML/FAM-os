import unittest
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import (
    DegradationDisposition, DegradationImpact, DegradationKind, DegradationNotice,
    ExecutionPlan, FailureComponent, PlanStep, PlanStepKind, PlanTransition,
    StepOutcome, TaskRequest, TerminalDisposition,
)
from fam_os.core.lifecycle import (
    ControlCommand, ControlKind, ControlRejection, InMemoryControlReplayRegistry,
    InMemoryDeadlinePolicyRegistry, InMemoryPlanStateRepository, PlanControlService,
    PlanDeadlinePolicy, PlanEvidenceKind, PlanLifecycleService, PlanRejection,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RouteName, RoutingResult


NOW = datetime(2026, 7, 16, 21, tzinfo=timezone.utc)


class CoreControlTransitionTests(unittest.TestCase):
    def test_cancellation_uses_declared_edge_and_is_absorbing(self):
        lifecycle, controls, route = runtime()
        result = controls.cancel(command(route, "cancel-1"))
        self.assertEqual(ControlKind.CANCELLED, result.kind)
        self.assertEqual("withhold", result.snapshot.current_step_id)
        self.assertEqual(PlanEvidenceKind.CANCELLATION, result.snapshot.events[-1].evidence_refs[0].kind)
        again = controls.cancel(command(route, "cancel-2", revision=1))
        self.assertEqual(PlanRejection.TERMINAL, again.rejection)

    def test_timeout_requires_trusted_due_deadline(self):
        _lifecycle, early, route = runtime(deadline=NOW + timedelta(seconds=1))
        self.assertEqual(ControlRejection.NOT_DUE, early.timeout(command(route, "timeout-1")).rejection)
        _lifecycle, due, route = runtime(deadline=NOW)
        result = due.timeout(command(route, "timeout-1"))
        self.assertEqual(ControlKind.TIMED_OUT, result.kind)
        self.assertEqual(PlanEvidenceKind.TIMEOUT, result.snapshot.events[-1].evidence_refs[0].kind)

    def test_degradation_is_reference_only_and_follows_unavailable(self):
        _lifecycle, controls, route = runtime()
        notice = degradation()
        result = controls.degrade(command(route, "degradation-1", degradation=notice))
        self.assertEqual(ControlKind.DEGRADED, result.kind)
        self.assertEqual(notice, result.degradation)
        self.assertNotIn(notice.safe_message, repr(result.snapshot))
        self.assertEqual(notice.degradation_id, result.snapshot.events[-1].evidence_refs[0].reference_id)

    def test_stale_control_does_not_burn_replay_id(self):
        _lifecycle, controls, route = runtime()
        stale = controls.cancel(command(route, "cancel-1", revision=2))
        accepted = controls.cancel(command(route, "cancel-1"))
        self.assertEqual(PlanRejection.REVISION_CONFLICT, stale.rejection)
        self.assertEqual(ControlKind.CANCELLED, accepted.kind)

    def test_missing_edge_rejects_without_reserving(self):
        lifecycle, controls, route = runtime(include_cancel=False)
        rejected = controls.cancel(command(route, "control-1"))
        self.assertEqual(PlanRejection.ILLEGAL_OUTCOME, rejected.rejection)
        timeout = controls.timeout(command(route, "control-1"))
        self.assertEqual(ControlKind.TIMED_OUT, timeout.kind)
        self.assertTrue(lifecycle.repository.get("instance-1").terminal)


def runtime(deadline=NOW, include_cancel=True):
    route = routed()
    lifecycle = PlanLifecycleService(
        InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: "instance-1", event_id_factory=event_ids(),
    )
    lifecycle.start(route, plan(include_cancel))
    controls = PlanControlService(
        lifecycle,
        InMemoryDeadlinePolicyRegistry((PlanDeadlinePolicy("plan-1", deadline),)),
        InMemoryControlReplayRegistry(), clock=lambda: NOW,
    )
    return lifecycle, controls, route


def plan(include_cancel=True):
    route = route_decision()
    steps = (
        PlanStep("work", PlanStepKind.INFERENCE, "Work", ("language",)),
        terminal("release", TerminalDisposition.RELEASE),
        terminal("withhold", TerminalDisposition.WITHHOLD),
    )
    transitions = [
        PlanTransition("work", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("work", StepOutcome.UNAVAILABLE, "withhold"),
    ]
    if include_cancel:
        transitions.append(PlanTransition("work", StepOutcome.CANCELLED, "withhold"))
    return ExecutionPlan("plan-1", "request-1", route, "work", steps, tuple(transitions))


def terminal(step_id, disposition):
    return PlanStep(step_id, PlanStepKind.FINALIZE, step_id, terminal_disposition=disposition)


def routed():
    request = TaskRequest("request-1", "Answer", ("language",))
    permission = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", ("language",),
        NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW)
    return RoutedTaskRequest(admitted, RoutingResult(route_decision()))


def route_decision():
    return RouteDecision(RouteName.KERNEL, 1.0, "Language task.", ("language",))


def command(route, control_id, revision=0, degradation=None):
    return ControlCommand(control_id, "instance-1", revision, route, degradation)


def degradation():
    return DegradationNotice(
        "degradation-1", DegradationKind.QUALITY_REDUCED,
        "core.quality.reduced", "Quality was reduced.", FailureComponent.CORE,
        DegradationImpact.MEDIUM, DegradationDisposition.WITHHOLD,
    )


def event_ids():
    values = iter(range(10))
    return lambda: f"event-{next(values)}"


if __name__ == "__main__":
    unittest.main()
