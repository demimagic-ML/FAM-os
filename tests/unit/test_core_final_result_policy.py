import unittest
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import (
    ExecutionPlan, PlanStep, PlanStepKind, PlanTransition, ResultStatus,
    StepOutcome, TaskRequest, TerminalDisposition,
)
from fam_os.core.lifecycle import (
    AcceptanceEvidenceRecord, CandidateEvidenceRecord, FinalResultPolicy,
    ControlCommand, InMemoryFinalEvidenceRegistry, InMemoryPlanStateRepository, PlanEvidenceKind,
    PlanEvidenceReference, PlanLifecycleService,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RouteName, RoutingResult
from tests.unit.test_core_control_transitions import degradation, runtime as control_runtime


NOW = datetime(2026, 7, 16, 22, tzinfo=timezone.utc)


class CoreFinalResultPolicyTests(unittest.TestCase):
    def test_verified_release_requires_linked_passing_acceptance(self):
        snapshot = released(verified=True)
        registry = InMemoryFinalEvidenceRegistry(
            (candidate(),),
            (AcceptanceEvidenceRecord("verification-1", "candidate-1", ("tests",), True),),
        )
        outcome = FinalResultPolicy(registry).assemble(snapshot)
        self.assertEqual(ResultStatus.VERIFIED, outcome.result.status)
        self.assertEqual("trusted output", outcome.result.content)
        self.assertEqual(("candidate-1", "verification-1"), outcome.result.evidence_ids)

    def test_verified_release_rejects_missing_failed_or_cross_candidate_acceptance(self):
        snapshot = released(verified=True)
        cases = (
            (),
            (AcceptanceEvidenceRecord("verification-1", "other", ("tests",), True),),
            (AcceptanceEvidenceRecord("verification-1", "candidate-1", ("tests",), False),),
        )
        for acceptances in cases:
            with self.subTest(acceptances=acceptances):
                outcome = FinalResultPolicy(
                    InMemoryFinalEvidenceRegistry((candidate(),), acceptances)
                ).assemble(snapshot)
                self.assertEqual("final.acceptance_evidence_required", outcome.rejection_code)

    def test_completed_release_content_comes_only_from_registry(self):
        snapshot = released(verified=False)
        outcome = FinalResultPolicy(
            InMemoryFinalEvidenceRegistry((candidate(),))
        ).assemble(snapshot)
        self.assertEqual(ResultStatus.COMPLETED, outcome.result.status)
        self.assertEqual("trusted output", outcome.result.content)

    def test_wrong_request_candidate_and_nonterminal_snapshot_are_rejected(self):
        snapshot = released(verified=False)
        wrong = CandidateEvidenceRecord("candidate-1", "other", "plan-1", "forged")
        self.assertEqual(
            "final.invalid_candidate_evidence",
            FinalResultPolicy(InMemoryFinalEvidenceRegistry((wrong,))).assemble(snapshot).rejection_code,
        )
        active = started(False)
        self.assertEqual(
            "final.nonterminal",
            FinalResultPolicy(InMemoryFinalEvidenceRegistry()).assemble(active).rejection_code,
        )

    def test_cancellation_and_timeout_are_content_free_safe_results(self):
        for method, expected_code in (("cancel", "core.request.cancelled"), ("timeout", "core.request.timed_out")):
            lifecycle, controls, route = control_runtime()
            snapshot = getattr(controls, method)(ControlCommand(f"{method}-1", "instance-1", 0, route)).snapshot
            result = FinalResultPolicy(InMemoryFinalEvidenceRegistry()).assemble(snapshot).result
            self.assertEqual(ResultStatus.WITHHELD, result.status)
            self.assertIsNone(result.content)
            self.assertEqual(expected_code, result.failure.code)

    def test_withholding_degradation_blocks_even_release(self):
        snapshot = released(verified=False, degradation_ref="degradation-1")
        notice = degradation()
        registry = InMemoryFinalEvidenceRegistry((candidate(),), degradations=(notice,))
        result = FinalResultPolicy(registry).assemble(snapshot).result
        self.assertEqual(ResultStatus.WITHHELD, result.status)
        self.assertIsNone(result.content)
        self.assertEqual(notice.safe_message, result.reason)

    def test_failed_candidate_registry_content_never_leaks_on_withhold(self):
        lifecycle, controls, route = control_runtime()
        snapshot = controls.cancel(ControlCommand("cancel-1", "instance-1", 0, route)).snapshot
        failed = CandidateEvidenceRecord("cancel-1", "request-1", "plan-1", "unsafe candidate")
        result = FinalResultPolicy(InMemoryFinalEvidenceRegistry((failed,))).assemble(snapshot).result
        self.assertIsNone(result.content)
        self.assertNotIn("unsafe candidate", repr(result))


def released(verified, degradation_ref=None):
    lifecycle = started(verified, return_lifecycle=True)
    if verified:
        lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED)
    revision = 1 if verified else 0
    refs = [PlanEvidenceReference("candidate-1", PlanEvidenceKind.RELEASE_CANDIDATE, "code")]
    if verified:
        refs.append(PlanEvidenceReference("verification-1", PlanEvidenceKind.VERIFICATION_PASS, "code"))
    if degradation_ref:
        refs.append(PlanEvidenceReference(degradation_ref, PlanEvidenceKind.DEGRADATION, "code"))
    return lifecycle.advance("instance-1", revision, StepOutcome.SUCCEEDED, tuple(refs)).snapshot


def started(verified, return_lifecycle=False):
    route = routed()
    lifecycle = PlanLifecycleService(
        InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: "instance-1", event_id_factory=event_ids(),
    )
    lifecycle.start(route, plan(verified))
    return lifecycle if return_lifecycle else lifecycle.repository.get("instance-1")


def plan(verified):
    steps = [PlanStep("generate", PlanStepKind.INFERENCE, "Generate", ("code",))]
    transitions = []
    if verified:
        steps.append(PlanStep("verify", PlanStepKind.VERIFY, "Verify", acceptance_ids=("tests",)))
        transitions.append(PlanTransition("generate", StepOutcome.SUCCEEDED, "verify"))
        source = "verify"
    else:
        source = "generate"
    steps.append(PlanStep("release", PlanStepKind.FINALIZE, "Release", terminal_disposition=TerminalDisposition.RELEASE))
    transitions.append(PlanTransition(source, StepOutcome.SUCCEEDED, "release"))
    return ExecutionPlan("plan-1", "request-1", route_decision(), "generate", tuple(steps), tuple(transitions), verified)


def routed():
    request = TaskRequest("request-1", "Generate code", ("code",), True)
    permission = RequestPermissionContext("principal-1", "session-1", "authority-1", ("code",), NOW + timedelta(hours=1))
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW)
    return RoutedTaskRequest(admitted, RoutingResult(route_decision()))


def route_decision():
    return RouteDecision(RouteName.CODE, 1.0, "Code task.", ("code",))


def candidate():
    return CandidateEvidenceRecord("candidate-1", "request-1", "plan-1", "trusted output")


def event_ids():
    values = iter(range(10))
    return lambda: f"event-{next(values)}"


if __name__ == "__main__":
    unittest.main()
