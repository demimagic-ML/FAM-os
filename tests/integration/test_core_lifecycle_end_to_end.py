import unittest
from datetime import datetime, timedelta, timezone

from fam_os.applications import ConfirmationDecision
from fam_os.core.admission import (
    InMemoryRequestAuthorityRegistry, InMemoryRequestReplayRegistry,
    RequestAdmissionService, RequestAuthorityGrant, RequestIdentity,
)
from fam_os.core.contracts import (
    ExecutionPlan, PlanStep, PlanStepKind, PlanTransition, ResultStatus,
    StepOutcome, TaskRequest, TerminalDisposition,
)
from fam_os.core.lifecycle import (
    AcceptanceEvidenceRecord, CandidateEvidenceRecord, ConfirmationDisposition,
    FinalResultPolicy, InMemoryFinalEvidenceRegistry, InMemoryPlanStateRepository,
    PlanEvidenceKind, PlanEvidenceReference, PlanLifecycleService,
)
from fam_os.core.routing import CoreRoutingService
from fam_os.routing import RouteDecision, RouteName, RoutingResult
from tests.unit.test_core_application_steps import ACTION
from tests.unit.test_core_attempt_transitions import command as attempt_command, runtime as attempt_runtime, service as attempt_service
from tests.unit.test_core_confirmation_transitions import command as confirmation_command, confirmation_runtime, decision
from tests.unit.test_core_control_transitions import ControlCommand, degradation, runtime as control_runtime


NOW = datetime(2026, 7, 16, 23, tzinfo=timezone.utc)


class Router:
    def route(self, request):
        return RoutingResult(RouteDecision(RouteName.CODE, 1.0, "Verified code.", request.required_capabilities))


class CoreLifecycleEndToEndTests(unittest.TestCase):
    def test_admission_routing_plan_verification_and_release(self):
        request = TaskRequest("request-e2e", "Generate verified code", ("code",), True)
        grant = RequestAuthorityGrant(
            "authority-1", "principal-1", "session-1", ("code",),
            NOW - timedelta(minutes=1), NOW + timedelta(hours=1),
        )
        admission = RequestAdmissionService(
            InMemoryRequestAuthorityRegistry((grant,)), InMemoryRequestReplayRegistry(),
            clock=lambda: NOW, admission_id_factory=lambda: "admission-e2e",
            error_id_factory=lambda: "error-e2e",
        ).admit(request, RequestIdentity("principal-1", "session-1", "authority-1"))
        routed = CoreRoutingService(
            Router(), clock=lambda: NOW, error_id_factory=lambda: "route-error"
        ).route(admission.admitted).routed
        lifecycle = PlanLifecycleService(
            InMemoryPlanStateRepository(), clock=lambda: NOW,
            instance_id_factory=lambda: "instance-e2e", event_id_factory=event_ids(),
        )
        lifecycle.start(routed, verified_plan(routed.routing.decision))
        lifecycle.advance("instance-e2e", 0, StepOutcome.SUCCEEDED)
        refs = (
            PlanEvidenceReference("candidate-e2e", PlanEvidenceKind.RELEASE_CANDIDATE, "code"),
            PlanEvidenceReference("verification-e2e", PlanEvidenceKind.VERIFICATION_PASS, "code"),
        )
        terminal = lifecycle.advance("instance-e2e", 1, StepOutcome.SUCCEEDED, refs).snapshot
        registry = InMemoryFinalEvidenceRegistry(
            (CandidateEvidenceRecord("candidate-e2e", "request-e2e", "plan-e2e", "verified output"),),
            (AcceptanceEvidenceRecord("verification-e2e", "candidate-e2e", ("tests",), True),),
        )
        result = FinalResultPolicy(registry).assemble(terminal).result

        self.assertEqual(ResultStatus.VERIFIED, result.status)
        self.assertEqual("verified output", result.content)

    def test_denial_expiry_cancellation_timeout_and_degradation_withhold(self):
        _runtime, confirmation, _provider, route = confirmation_runtime()
        denied = confirmation.record_confirmation(confirmation_command(
            route, decision(ConfirmationDecision.DENIED, reason="Denied")
        ))
        denied_result = FinalResultPolicy(InMemoryFinalEvidenceRegistry()).assemble(denied.snapshot).result
        self.assertEqual(ResultStatus.WITHHELD, denied_result.status)

        _runtime, expiry, _provider, route = confirmation_runtime(
            clock=datetime(2026, 7, 17, 2, tzinfo=timezone.utc)
        )
        expired = expiry.record_confirmation(confirmation_command(
            route, decision(ConfirmationDecision.APPROVED)
        ))
        self.assertEqual(ConfirmationDisposition.EXPIRED, expired.disposition)
        self.assertIsNone(FinalResultPolicy(InMemoryFinalEvidenceRegistry()).assemble(expired.snapshot).result.content)

        for method in ("cancel", "timeout"):
            _lifecycle, controls, route = control_runtime()
            terminal = getattr(controls, method)(ControlCommand(f"{method}-e2e", "instance-1", 0, route)).snapshot
            self.assertIsNone(FinalResultPolicy(InMemoryFinalEvidenceRegistry()).assemble(terminal).result.content)

        _lifecycle, controls, route = control_runtime()
        notice = degradation()
        terminal = controls.degrade(ControlCommand(notice.degradation_id, "instance-1", 0, route, notice)).snapshot
        result = FinalResultPolicy(
            InMemoryFinalEvidenceRegistry(degradations=(notice,))
        ).assemble(terminal).result
        self.assertEqual(ResultStatus.WITHHELD, result.status)

    def test_budget_and_replay_rejections_never_release_failed_content(self):
        lifecycle, _attempts, route = attempt_runtime()
        lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED)
        from fam_os.core.lifecycle import InMemoryAttemptReplayRegistry
        blocked = attempt_service(
            lifecycle, InMemoryAttemptReplayRegistry(), max_repairs=0
        ).transition_after_failure(attempt_command(route, 1, "failed-e2e", "repair-e2e"))
        self.assertIsNotNone(blocked.rejection)
        self.assertEqual(
            "final.nonterminal",
            FinalResultPolicy(
                InMemoryFinalEvidenceRegistry((CandidateEvidenceRecord(
                    "failed-e2e", "request-1", "verified-code-plan-1", "unsafe failed content"
                ),))
            ).assemble(lifecycle.repository.get("instance-1")).rejection_code,
        )

        replay = __import__("fam_os.core.lifecycle", fromlist=["InMemoryConfirmationReplayRegistry"]).InMemoryConfirmationReplayRegistry()
        _r1, s1, _p1, route1 = confirmation_runtime(replay=replay)
        _r2, s2, _p2, route2 = confirmation_runtime(replay=replay)
        confirmation_value = decision(ConfirmationDecision.APPROVED)
        self.assertEqual(
            ConfirmationDisposition.APPROVED,
            s1.record_confirmation(confirmation_command(route1, confirmation_value)).disposition,
        )
        self.assertIsNotNone(
            s2.record_confirmation(confirmation_command(route2, confirmation_value)).rejection
        )


def verified_plan(route):
    steps = (
        PlanStep("generate", PlanStepKind.INFERENCE, "Generate", ("code",)),
        PlanStep("verify", PlanStepKind.VERIFY, "Verify", acceptance_ids=("tests",)),
        PlanStep("release", PlanStepKind.FINALIZE, "Release", terminal_disposition=TerminalDisposition.RELEASE),
    )
    transitions = (
        PlanTransition("generate", StepOutcome.SUCCEEDED, "verify"),
        PlanTransition("verify", StepOutcome.SUCCEEDED, "release"),
    )
    return ExecutionPlan("plan-e2e", "request-e2e", route, "generate", steps, transitions, True)


def event_ids():
    values = iter(range(10))
    return lambda: f"event-e2e-{next(values)}"


if __name__ == "__main__":
    unittest.main()
