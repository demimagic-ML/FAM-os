import unittest
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import StepOutcome, TaskRequest
from fam_os.core.lifecycle import (
    AttemptBudgetPolicy,
    AttemptKind,
    AttemptRejection,
    AttemptTransitionCommand,
    AttemptTransitionService,
    InMemoryAttemptPolicyRegistry,
    InMemoryAttemptReplayRegistry,
    InMemoryPlanStateRepository,
    PlanEvidenceKind,
    PlanLifecycleService,
    PlanRejection,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RoutingResult
from tests.unit.test_core_plan_contracts import _verified_code_plan


NOW = datetime(2026, 7, 16, 20, tzinfo=timezone.utc)


class CoreAttemptTransitionTests(unittest.TestCase):
    def test_repair_then_escalation_consume_distinct_unrolled_budgets(self):
        lifecycle, attempts, route = runtime()
        instance = lifecycle.repository.get("instance-1")
        verification = lifecycle.advance(instance.instance_id, 0, StepOutcome.SUCCEEDED).snapshot

        repair = attempts.transition_after_failure(command(route, verification.revision, "failed-1", "repair-1"))
        repair_verification = lifecycle.advance(
            repair.snapshot.instance_id, repair.snapshot.revision, StepOutcome.SUCCEEDED
        ).snapshot
        escalation = attempts.transition_after_failure(
            command(route, repair_verification.revision, "failed-2", "escalation-1")
        )

        self.assertEqual(AttemptKind.REPAIR, repair.kind)
        self.assertEqual("repair-inference", repair.snapshot.current_step_id)
        self.assertEqual(AttemptKind.ESCALATION, escalation.kind)
        self.assertEqual("escalation-inference", escalation.snapshot.current_step_id)
        kinds = tuple(
            ref.kind for event in escalation.snapshot.events for ref in event.evidence_refs
        )
        self.assertEqual(2, kinds.count(PlanEvidenceKind.FAILED_ATTEMPT))
        self.assertIn(PlanEvidenceKind.REPAIR_ATTEMPT, kinds)
        self.assertIn(PlanEvidenceKind.ESCALATION_ATTEMPT, kinds)
        self.assertFalse(hasattr(escalation, "candidate"))

    def test_zero_repair_budget_blocks_without_mutating_or_reserving(self):
        lifecycle, _attempts, route = runtime()
        verification = lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED).snapshot
        replay = InMemoryAttemptReplayRegistry()
        blocked = service(lifecycle, replay, max_repairs=0).transition_after_failure(
            command(route, 1, "failed-1", "repair-1")
        )
        self.assertEqual(verification, lifecycle.repository.get("instance-1"))
        accepted = service(lifecycle, replay).transition_after_failure(
            command(route, 1, "failed-1", "repair-1")
        )
        self.assertEqual(AttemptRejection.BUDGET_EXHAUSTED, blocked.rejection)
        self.assertEqual(AttemptKind.REPAIR, accepted.kind)

    def test_stale_command_does_not_burn_attempt_ids(self):
        lifecycle, _attempts, route = runtime()
        lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED)
        replay = InMemoryAttemptReplayRegistry()
        attempts = service(lifecycle, replay)
        stale = attempts.transition_after_failure(command(route, 0, "failed-1", "repair-1"))
        accepted = attempts.transition_after_failure(command(route, 1, "failed-1", "repair-1"))
        self.assertEqual(PlanRejection.REVISION_CONFLICT, stale.rejection)
        self.assertEqual(AttemptKind.REPAIR, accepted.kind)

    def test_policy_must_classify_declared_failure_target(self):
        lifecycle, _attempts, route = runtime()
        lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED)
        policy = AttemptBudgetPolicy("verified-code-plan-1", (), (), 0, 0)
        attempts = AttemptTransitionService(
            lifecycle, InMemoryAttemptPolicyRegistry((policy,)),
            InMemoryAttemptReplayRegistry(),
        )
        result = attempts.transition_after_failure(command(route, 1, "failed-1", "next-1"))
        self.assertEqual(AttemptRejection.INVALID_STEP, result.rejection)

    def test_attempt_identity_cannot_be_reused_across_plans(self):
        replay = InMemoryAttemptReplayRegistry()
        lifecycle1, _attempts1, route1 = runtime()
        lifecycle2, _attempts2, route2 = runtime()
        lifecycle1.advance("instance-1", 0, StepOutcome.SUCCEEDED)
        lifecycle2.advance("instance-1", 0, StepOutcome.SUCCEEDED)
        first = service(lifecycle1, replay).transition_after_failure(
            command(route1, 1, "failed-1", "repair-1")
        )
        second = service(lifecycle2, replay).transition_after_failure(
            command(route2, 1, "failed-1", "repair-1")
        )
        self.assertEqual(AttemptKind.REPAIR, first.kind)
        self.assertEqual(AttemptRejection.REPLAYED, second.rejection)


def runtime():
    route = routed()
    lifecycle = PlanLifecycleService(
        InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: "instance-1",
        event_id_factory=event_ids(),
    )
    lifecycle.start(route, _verified_code_plan())
    return lifecycle, service(lifecycle, InMemoryAttemptReplayRegistry()), route


def service(lifecycle, replay, max_repairs=1):
    policy = AttemptBudgetPolicy(
        "verified-code-plan-1", ("repair-inference",),
        ("escalation-inference",), max_repairs, 1,
    )
    return AttemptTransitionService(
        lifecycle, InMemoryAttemptPolicyRegistry((policy,)), replay
    )


def routed():
    request = TaskRequest("request-1", "Write verified code", ("code",), True)
    permission = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", ("code",),
        NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW)
    plan = _verified_code_plan()
    return RoutedTaskRequest(admitted, RoutingResult(plan.route))


def command(route, revision, failed_id, next_id):
    return AttemptTransitionCommand("instance-1", revision, route, failed_id, next_id)


def event_ids():
    counter = iter(range(20))
    return lambda: f"event-{next(counter)}"


if __name__ == "__main__":
    unittest.main()
