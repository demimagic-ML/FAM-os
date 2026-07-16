import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import (
    ExecutionPlan,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    StepOutcome,
    TaskRequest,
    TerminalDisposition,
)
from fam_os.core.lifecycle import (
    InMemoryPlanStateRepository,
    PlanEventKind,
    PlanInstanceSnapshot,
    PlanLifecycleEvent,
    PlanLifecycleService,
    PlanRejection,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RouteName, RoutingResult


NOW = datetime(2026, 7, 16, 18, tzinfo=timezone.utc)


def routed(decision=None):
    decision = decision or route()
    request = TaskRequest("request-1", "Read the file", ("files.read",))
    permission = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", ("files.read",),
        NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW)
    return RoutedTaskRequest(admitted, RoutingResult(decision))


def route(capabilities=("files.read",)):
    return RouteDecision(RouteName.RETRIEVAL, 0.9, "Read trusted file.", capabilities)


def plan(request_id="request-1", decision=None):
    decision = decision or route()
    steps = (
        PlanStep("read", PlanStepKind.OBSERVE, "Read file", decision.required_capabilities),
        terminal("release", TerminalDisposition.RELEASE),
        terminal("withhold", TerminalDisposition.WITHHOLD),
    )
    transitions = (
        PlanTransition("read", StepOutcome.SUCCEEDED, "release"),
        PlanTransition("read", StepOutcome.FAILED, "withhold"),
    )
    return ExecutionPlan("plan-1", request_id, decision, "read", steps, transitions)


def terminal(step_id, disposition):
    return PlanStep(
        step_id, PlanStepKind.FINALIZE, disposition.value,
        terminal_disposition=disposition,
    )


def service(repository=None):
    ids = iter(("instance-1", "event-0", "event-1", "event-2"))
    return PlanLifecycleService(
        repository or InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: next(ids), event_id_factory=lambda: next(ids),
    )


class CorePlanLifecycleTests(unittest.TestCase):
    def test_starts_bound_plan_with_minimal_persisted_state(self):
        repository = InMemoryPlanStateRepository()
        result = service(repository).start(routed(), plan())

        self.assertIsNone(result.rejection)
        self.assertEqual("read", result.snapshot.current_step_id)
        self.assertEqual(0, result.snapshot.revision)
        self.assertEqual(PlanEventKind.STARTED, result.snapshot.events[0].kind)
        self.assertEqual(result.snapshot, repository.get("instance-1"))
        self.assertFalse(hasattr(result.snapshot, "admitted"))
        self.assertFalse(hasattr(result.snapshot, "prompt"))

    def test_rejects_request_route_and_capability_binding_mismatch(self):
        cases = (
            plan(request_id="request-2"),
            plan(decision=RouteDecision(RouteName.CODE, 0.9, "Different.", ("files.read",))),
            plan(decision=route(("files.read", "files.write"))),
        )
        for candidate in cases:
            with self.subTest(plan=candidate):
                result = service().start(routed(), candidate)
                self.assertEqual(PlanRejection.INVALID_BINDING, result.rejection)

    def test_selects_success_and_failure_branches_deterministically(self):
        for outcome, target, disposition in (
            (StepOutcome.SUCCEEDED, "release", TerminalDisposition.RELEASE),
            (StepOutcome.FAILED, "withhold", TerminalDisposition.WITHHOLD),
        ):
            runtime = service()
            started = runtime.start(routed(), plan()).snapshot
            advanced = runtime.advance(started.instance_id, 0, outcome)
            self.assertEqual(target, advanced.snapshot.current_step_id)
            self.assertEqual(disposition, advanced.snapshot.terminal_disposition)
            self.assertEqual(1, advanced.snapshot.revision)
            self.assertEqual(outcome, advanced.snapshot.events[-1].outcome)

    def test_illegal_outcome_does_not_mutate_state(self):
        repository = InMemoryPlanStateRepository()
        runtime = service(repository)
        started = runtime.start(routed(), plan()).snapshot

        rejected = runtime.advance(started.instance_id, 0, StepOutcome.CANCELLED)

        self.assertEqual(PlanRejection.ILLEGAL_OUTCOME, rejected.rejection)
        self.assertEqual(started, repository.get(started.instance_id))

    def test_stale_repeated_and_terminal_transitions_are_rejected(self):
        runtime = service()
        started = runtime.start(routed(), plan()).snapshot
        finished = runtime.advance(started.instance_id, 0, StepOutcome.SUCCEEDED).snapshot

        stale = runtime.advance(started.instance_id, 0, StepOutcome.SUCCEEDED)
        terminal_result = runtime.advance(finished.instance_id, 1, StepOutcome.SUCCEEDED)

        self.assertEqual(PlanRejection.REVISION_CONFLICT, stale.rejection)
        self.assertEqual(PlanRejection.TERMINAL, terminal_result.rejection)

    def test_missing_instance_and_duplicate_start_are_rejected(self):
        runtime = service()
        first = runtime.start(routed(), plan())
        duplicate = runtime.start(routed(), plan())
        missing = runtime.advance("missing", 0, StepOutcome.SUCCEEDED)

        self.assertIsNotNone(first.snapshot)
        self.assertEqual(PlanRejection.ALREADY_STARTED, duplicate.rejection)
        self.assertEqual(PlanRejection.NOT_FOUND, missing.rejection)

    def test_concurrent_reports_allow_only_one_transition(self):
        repository = InMemoryPlanStateRepository()
        runtime = PlanLifecycleService(
            repository, clock=lambda: NOW, instance_id_factory=lambda: "instance-1",
            event_id_factory=lambda: str(uuid4()),
        )
        started = runtime.start(routed(), plan()).snapshot
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(
                lambda _: runtime.advance(started.instance_id, 0, StepOutcome.SUCCEEDED),
                range(2),
            ))

        self.assertEqual(1, sum(result.snapshot is not None for result in results))
        self.assertEqual(
            1, sum(result.rejection is PlanRejection.REVISION_CONFLICT for result in results)
        )

    def test_snapshot_rejects_forged_event_history(self):
        runtime = service()
        started = runtime.start(routed(), plan()).snapshot
        forged = PlanLifecycleEvent(
            "forged", 1, NOW, PlanEventKind.TRANSITIONED, "withhold",
            "read", StepOutcome.SUCCEEDED, TerminalDisposition.WITHHOLD,
        )
        with self.assertRaisesRegex(ValueError, "illegal plan transition"):
            PlanInstanceSnapshot(
                started.instance_id, started.plan, "withhold", 1,
                started.events + (forged,), TerminalDisposition.WITHHOLD,
                started.authority_binding,
            )


if __name__ == "__main__":
    unittest.main()
