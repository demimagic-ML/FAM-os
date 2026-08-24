import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import (
    ExecutionPlan, PlanStep, PlanStepKind, PlanTransition, ResultKind, ResultStatus,
    StepOutcome, TaskRequest, TerminalDisposition,
)
from fam_os.core.lifecycle import (
    AcceptanceEvidenceRecord, CandidateEvidenceRecord, FinalResultPolicy,
    ControlCommand, InMemoryFinalEvidenceRegistry, InMemoryPlanStateRepository, PlanEvidenceKind,
    PlanEvidenceReference, PlanLifecycleService,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.fabric import (
    RemoteEvidenceDisposition,
    RemoteExecutionEvidence,
    RemoteVerificationOutcome,
    RemoteAttemptFailure,
    RemoteRecoveryDisposition,
    RemoteRecoveryEvidence,
)
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

    def test_remote_release_requires_matching_final_complete_evidence(self):
        snapshot = released(verified=True, remote_ref="remote-evidence-1")
        acceptance = AcceptanceEvidenceRecord(
            "verification-1", "candidate-1", ("tests",), True,
        )
        valid = remote_evidence()
        registry = InMemoryFinalEvidenceRegistry(
            (candidate(),), (acceptance,), remote_executions=(valid,),
        )
        result = FinalResultPolicy(registry).assemble(snapshot).result
        self.assertIn(valid.evidence_id, result.evidence_ids)

        for invalid in (
            replace(valid, candidate_id="candidate-other"),
            replace(
                valid,
                disposition=RemoteEvidenceDisposition.REJECTED,
                verification_outcome=RemoteVerificationOutcome.FAILED,
                acceptance_evidence_id=None,
            ),
        ):
            with self.subTest(invalid=invalid.disposition):
                outcome = FinalResultPolicy(InMemoryFinalEvidenceRegistry(
                    (candidate(),), (acceptance,), remote_executions=(invalid,),
                )).assemble(snapshot)
                self.assertEqual(
                    "final.invalid_remote_execution_evidence",
                    outcome.rejection_code,
                )

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

    def test_recovered_release_requires_matching_unchanged_acceptance_evidence(self):
        snapshot = released(verified=True, recovery_ref="remote-recovery-1")
        acceptance = AcceptanceEvidenceRecord(
            "verification-1", "candidate-1", ("tests",), True,
        )
        valid = recovery_evidence()
        registry = InMemoryFinalEvidenceRegistry(
            (candidate(),), (acceptance,), remote_recoveries=(valid,),
        )
        result = FinalResultPolicy(registry).assemble(snapshot).result
        self.assertIn(valid.evidence_id, result.evidence_ids)

        invalid = replace(valid, local_candidate_id="candidate-other")
        outcome = FinalResultPolicy(InMemoryFinalEvidenceRegistry(
            (candidate(),), (acceptance,), remote_recoveries=(invalid,),
        )).assemble(snapshot)
        self.assertEqual(
            "final.invalid_remote_recovery_evidence", outcome.rejection_code,
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

    def test_model_claim_without_action_execution_evidence_cannot_become_receipt(self):
        snapshot = released_action(with_execution_evidence=False)
        registry = InMemoryFinalEvidenceRegistry(
            (CandidateEvidenceRecord(
                "candidate-1", "request-1", "plan-1",
                "Done. I created the directory.",
            ),),
            (AcceptanceEvidenceRecord(
                "verification-1", "candidate-1",
                ("directory.exists-empty",), True,
            ),),
        )

        outcome = FinalResultPolicy(registry).assemble(snapshot)

        self.assertIsNone(outcome.result)
        self.assertEqual(
            "final.action_receipt_evidence_required", outcome.rejection_code,
        )

    def test_action_receipt_content_is_deterministic_not_model_content(self):
        snapshot = released_action(with_execution_evidence=True)
        registry = InMemoryFinalEvidenceRegistry(
            (CandidateEvidenceRecord(
                "candidate-1", "request-1", "plan-1",
                "Model prose must not become the receipt.",
            ),),
            (AcceptanceEvidenceRecord(
                "verification-1", "candidate-1",
                ("directory.exists-empty",), True,
            ),),
        )

        result = FinalResultPolicy(registry).assemble(snapshot).result

        self.assertEqual(ResultKind.ACTION_RECEIPT, result.result_kind)
        self.assertEqual(
            "The approved directory was created and independently verified.",
            result.content,
        )
        self.assertNotIn("Model prose", result.content)
        self.assertTrue(
            {"operation-1", "audit-requested", "audit-terminal"}
            <= set(result.evidence_ids),
        )


def released(verified, degradation_ref=None, remote_ref=None, recovery_ref=None):
    lifecycle = started(verified, return_lifecycle=True)
    if verified:
        lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED)
    revision = 1 if verified else 0
    refs = [PlanEvidenceReference("candidate-1", PlanEvidenceKind.RELEASE_CANDIDATE, "code")]
    if verified:
        refs.append(PlanEvidenceReference("verification-1", PlanEvidenceKind.VERIFICATION_PASS, "code"))
    if degradation_ref:
        refs.append(PlanEvidenceReference(degradation_ref, PlanEvidenceKind.DEGRADATION, "code"))
    if remote_ref:
        refs.append(PlanEvidenceReference(
            remote_ref, PlanEvidenceKind.REMOTE_EXECUTION, None,
        ))
    if recovery_ref:
        refs.append(PlanEvidenceReference(
            recovery_ref, PlanEvidenceKind.REMOTE_RECOVERY, None,
        ))
    return lifecycle.advance("instance-1", revision, StepOutcome.SUCCEEDED, tuple(refs)).snapshot


def released_action(with_execution_evidence):
    route = action_routed()
    lifecycle = PlanLifecycleService(
        InMemoryPlanStateRepository(), clock=lambda: NOW,
        instance_id_factory=lambda: "instance-1", event_id_factory=event_ids(),
    )
    lifecycle.start(route, action_plan())
    lifecycle.advance("instance-1", 0, StepOutcome.SUCCEEDED)
    references = ()
    if with_execution_evidence:
        references = (
            PlanEvidenceReference(
                "operation-1", PlanEvidenceKind.ACTION_RESULT,
                "os.directory.create", "grant-1",
            ),
            PlanEvidenceReference(
                "audit-requested", PlanEvidenceKind.ACTION_AUDIT,
                "os.directory.create", "grant-1",
            ),
            PlanEvidenceReference(
                "audit-terminal", PlanEvidenceKind.ACTION_AUDIT,
                "os.directory.create", "grant-1",
            ),
        )
    lifecycle.advance("instance-1", 1, StepOutcome.SUCCEEDED, references)
    return lifecycle.advance(
        "instance-1", 2, StepOutcome.SUCCEEDED,
        (
            PlanEvidenceReference(
                "candidate-1", PlanEvidenceKind.RELEASE_CANDIDATE, None,
            ),
            PlanEvidenceReference(
                "verification-1", PlanEvidenceKind.VERIFICATION_PASS, None,
            ),
        ),
    ).snapshot


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


def action_plan():
    capability = "os.directory.create"
    acceptance = "directory.exists-empty"
    steps = (
        PlanStep("generate", PlanStepKind.INFERENCE, "Generate", (capability,)),
        PlanStep(
            "execute", PlanStepKind.EXECUTE_ACTION, "Create directory",
            (capability,), (acceptance,),
        ),
        PlanStep("verify", PlanStepKind.VERIFY, "Verify", acceptance_ids=(acceptance,)),
        PlanStep(
            "release", PlanStepKind.FINALIZE, "Release",
            terminal_disposition=TerminalDisposition.RELEASE,
        ),
    )
    transitions = (
        PlanTransition("generate", StepOutcome.SUCCEEDED, "execute"),
        PlanTransition("execute", StepOutcome.SUCCEEDED, "verify"),
        PlanTransition("verify", StepOutcome.SUCCEEDED, "release"),
    )
    return ExecutionPlan(
        "plan-1", "request-1", action_route_decision(), "generate",
        steps, transitions, True,
    )


def routed():
    request = TaskRequest("request-1", "Generate code", ("code",), True)
    permission = RequestPermissionContext("principal-1", "session-1", "authority-1", ("code",), NOW + timedelta(hours=1))
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW)
    return RoutedTaskRequest(admitted, RoutingResult(route_decision()))


def action_routed():
    capability = "os.directory.create"
    request = TaskRequest("request-1", "Create the directory", (capability,), True)
    permission = RequestPermissionContext(
        "principal-1", "session-1", "authority-1", (capability,),
        NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest("admission-1", request, permission, NOW)
    return RoutedTaskRequest(admitted, RoutingResult(action_route_decision()))


def route_decision():
    return RouteDecision(RouteName.CODE, 1.0, "Code task.", ("code",))


def action_route_decision():
    return RouteDecision(
        RouteName.KERNEL, 1.0, "Application action.",
        ("os.directory.create",),
    )


def candidate():
    return CandidateEvidenceRecord("candidate-1", "request-1", "plan-1", "trusted output")


def remote_evidence():
    return RemoteExecutionEvidence(
        evidence_id="remote-evidence-1", instance_id="instance-1",
        request_id="request-1", remote_plan_id="remote-plan-1",
        remote_plan_sha256="1" * 64, execution_id="remote-execution-1",
        execution_request_sha256="2" * 64, execution_result_sha256="3" * 64,
        enrollment_id="enrollment-1", peer_device_id="device-1",
        expert_id="expert-1", model_ref="model:q4", expert_tier="economical",
        capability_declaration_id="capability-1",
        context_evidence_id="context-evidence-1", context_id="context-1",
        context_content_bytes=10, context_content_sha256="4" * 64,
        context_receipt_sha256="5" * 64,
        budget_reservation_id="budget-1", budget_attempt_id="attempt-1",
        candidate_id="candidate-1", candidate_sha256="6" * 64,
        result_content_bytes=14, result_content_sha256="6" * 64,
        disposition=RemoteEvidenceDisposition.RELEASED,
        verification_outcome=RemoteVerificationOutcome.PASSED,
        acceptance_id="tests", acceptance_evidence_id="verification-1",
        verification_run_id=None, authenticated_at=NOW,
        finalized_at=NOW + timedelta(seconds=1),
    )


def recovery_evidence():
    return RemoteRecoveryEvidence(
        "remote-recovery-1", "instance-1", "request-1", "remote-plan-1",
        "budget-remote", "attempt-remote", RemoteAttemptFailure.DISCONNECTED,
        "7" * 64, "7" * 64, True, True,
        "selection-local", "local:q4", "economical",
        "budget-local", "attempt-local", "candidate-1",
        RemoteRecoveryDisposition.RECOVERED,
        ("remote.disconnected", "acceptance.unchanged", "fallback.local"),
        NOW, NOW + timedelta(seconds=1),
    )


def event_ids():
    values = iter(range(10))
    return lambda: f"event-{next(values)}"


if __name__ == "__main__":
    unittest.main()
