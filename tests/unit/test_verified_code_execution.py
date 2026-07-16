import unittest

from fam_os.core.contracts import (
    DegradationDisposition,
    DegradationKind,
    FailureCategory,
    ResultStatus,
    TaskRequest,
)
from fam_os.core.execution import (
    AttemptKind,
    ExecutionStatus,
    GenerationSettings,
    RepairContext,
    VerifiedCodeExecution,
    VerifiedCodePolicy,
)
from fam_os.core.execution.attempt import AttemptExecutor
from fam_os.core.execution.placement import PlacementExecutor
from fam_os.experts import ExpertTier
from fam_os.routing import RouteName
from fam_os.verification import VerificationStatus

from tests.unit.execution_fakes import (
    FakeCatalog,
    FakePlanner,
    FakeRouter,
    FakeRuntime,
    FakeVerifier,
    expert,
    plan,
)


class VerifiedCodeExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.economical = expert("economical", "code:7b", ExpertTier.ECONOMICAL)
        self.escalation = expert("escalation", "code:14b", ExpertTier.ESCALATION)
        self.router_expert = expert("router", "router:small", ExpertTier.MICRO)
        self.request = TaskRequest(
            "request-1",
            "Implement a stable sort",
            ("python",),
            verification_required=True,
        )

    def build(
        self,
        contents: list[str],
        statuses: list[VerificationStatus],
        route: RouteName = RouteName.CODE,
    ) -> tuple[VerifiedCodeExecution, FakeRuntime, FakeVerifier, FakeRouter, FakePlanner]:
        runtime = FakeRuntime(contents)
        verifier = FakeVerifier(statuses)
        router = FakeRouter(route)
        catalog = FakeCatalog((self.economical, self.escalation, self.router_expert))
        planner = FakePlanner(
            (
                plan("economical"),
                plan("escalation", ("economical", "router")),
            )
        )
        placement = PlacementExecutor(runtime, catalog, planner)
        use_case = VerifiedCodeExecution(
            router,
            catalog,
            placement,
            AttemptExecutor(runtime, verifier),
        )
        return use_case, runtime, verifier, router, planner

    @staticmethod
    def policy(
        repairs: int = 1,
        escalate: bool = True,
        escalation_repairs: int = 1,
    ) -> VerifiedCodePolicy:
        return VerifiedCodePolicy(
            economical_expert_id="economical",
            generation=GenerationSettings(1_024),
            repair_attempts=repairs,
            escalate_on_failure=escalate,
            escalation_expert_id="escalation" if escalate else None,
            escalation_repair_attempts=escalation_repairs,
            repair_guidance="preserve the public API",
        )

    def test_releases_initial_candidate_only_after_pass(self) -> None:
        use_case, runtime, _, router, planner = self.build(
            ["candidate-1"],
            [VerificationStatus.PASSED],
        )

        outcome = use_case.execute(self.request, self.policy())

        self.assertEqual(outcome.status, ExecutionStatus.VERIFIED)
        self.assertEqual(outcome.result.status, ResultStatus.VERIFIED)
        self.assertEqual(outcome.result.content, "candidate-1")
        self.assertEqual(
            outcome.result.evidence_ids,
            (outcome.attempts[-1].verification.verification_id,),
        )
        self.assertEqual([item.kind for item in outcome.attempts], [AttemptKind.ECONOMICAL])
        self.assertEqual(router.requests[0].required_capabilities, ("python",))
        self.assertEqual(planner.requested, ["economical"])
        self.assertEqual(runtime.unloaded, [])

    def test_bounded_economical_repair_can_release(self) -> None:
        use_case, runtime, _, _, _ = self.build(
            ["bad", "fixed"],
            [VerificationStatus.FAILED, VerificationStatus.PASSED],
        )

        outcome = use_case.execute(self.request, self.policy(repairs=2))

        self.assertEqual(outcome.status, ExecutionStatus.VERIFIED_AFTER_REPAIR)
        self.assertEqual(outcome.result.content, "fixed")
        self.assertEqual(
            [item.kind for item in outcome.attempts],
            [AttemptKind.ECONOMICAL, AttemptKind.REPAIR],
        )
        self.assertIn("assertion failed", runtime.requests[1].messages[1].content)

    def test_repair_receives_explicit_tests_and_failure_examples(self) -> None:
        use_case, runtime, _, _, _ = self.build(
            ["bad", "fixed"],
            [VerificationStatus.FAILED, VerificationStatus.PASSED],
        )
        policy = VerifiedCodePolicy(
            economical_expert_id="economical",
            generation=GenerationSettings(1_024),
            repair_attempts=1,
            escalate_on_failure=False,
            repair_context=RepairContext(
                "assert stable_topological_sort({'B': []}) == ['B']",
                ("{'B': ['D'], 'A': ['D'], 'D': []} -> ['B', 'A', 'D']",),
            ),
        )

        use_case.execute(self.request, policy)

        repair = runtime.requests[1].messages[1].content
        self.assertIn("Trusted test source", repair)
        self.assertIn("stable_topological_sort", repair)
        self.assertIn("['B', 'A', 'D']", repair)
        self.assertIn("assertion failed", repair)

    def test_scheduler_evictions_run_before_escalation(self) -> None:
        use_case, runtime, _, _, planner = self.build(
            ["bad", "large-fixed"],
            [VerificationStatus.FAILED, VerificationStatus.PASSED],
        )

        outcome = use_case.execute(self.request, self.policy(repairs=0))

        self.assertEqual(outcome.status, ExecutionStatus.VERIFIED_AFTER_ESCALATION)
        self.assertEqual(runtime.unloaded, ["code:7b", "router:small"])
        self.assertEqual(outcome.evicted_expert_ids, ("economical", "router"))
        self.assertEqual(planner.requested, ["economical", "escalation"])
        self.assertEqual([request.model_ref for request in runtime.requests], ["code:7b", "code:14b"])

    def test_escalation_repair_can_release(self) -> None:
        use_case, _, _, _, _ = self.build(
            ["bad", "large-bad", "large-fixed"],
            [
                VerificationStatus.FAILED,
                VerificationStatus.FAILED,
                VerificationStatus.PASSED,
            ],
        )

        outcome = use_case.execute(
            self.request,
            self.policy(repairs=0, escalation_repairs=1),
        )

        self.assertEqual(outcome.status, ExecutionStatus.VERIFIED_AFTER_ESCALATION_REPAIR)
        self.assertEqual(outcome.result.content, "large-fixed")
        self.assertEqual(outcome.attempts[-1].kind, AttemptKind.ESCALATION_REPAIR)

    def test_exhausted_candidates_are_retained_but_never_released(self) -> None:
        candidates = ["bad-1", "bad-2", "bad-3", "bad-4"]
        use_case, _, _, _, _ = self.build(
            candidates.copy(),
            [VerificationStatus.FAILED] * 4,
        )

        outcome = use_case.execute(self.request, self.policy())

        self.assertEqual(outcome.status, ExecutionStatus.VERIFICATION_FAILED)
        self.assertEqual(outcome.result.status, ResultStatus.WITHHELD)
        self.assertIsNone(outcome.result.content)
        self.assertFalse(outcome.result.verified)
        self.assertEqual(outcome.result.failure.category, FailureCategory.VERIFICATION_FAILED)
        self.assertEqual(outcome.result.failure.evidence_ids, outcome.result.evidence_ids)
        self.assertEqual([item.candidate for item in outcome.attempts], candidates)
        self.assertEqual(
            [item.kind for item in outcome.attempts],
            [
                AttemptKind.ECONOMICAL,
                AttemptKind.REPAIR,
                AttemptKind.ESCALATION,
                AttemptKind.ESCALATION_REPAIR,
            ],
        )

    def test_policy_can_withhold_without_escalating(self) -> None:
        use_case, runtime, _, _, planner = self.build(
            ["bad"],
            [VerificationStatus.FAILED],
        )

        outcome = use_case.execute(
            self.request,
            self.policy(repairs=0, escalate=False),
        )

        self.assertEqual(outcome.status, ExecutionStatus.VERIFICATION_FAILED)
        self.assertIsNone(outcome.result.content)
        self.assertEqual(planner.requested, ["economical"])
        self.assertEqual(runtime.unloaded, [])

    def test_verifier_error_halts_repairs_and_escalation(self) -> None:
        use_case, runtime, verifier, _, planner = self.build(
            ["candidate"],
            [VerificationStatus.ERROR],
        )

        outcome = use_case.execute(self.request, self.policy(repairs=3))

        self.assertEqual(outcome.status, ExecutionStatus.ERROR)
        self.assertEqual(outcome.result.status, ResultStatus.FAILED)
        self.assertIsNone(outcome.result.content)
        self.assertEqual(len(verifier.requests), 1)
        self.assertEqual(len(runtime.requests), 1)
        self.assertEqual(planner.requested, ["economical"])

    def test_non_code_route_never_activates_an_expert(self) -> None:
        use_case, runtime, verifier, _, planner = self.build([], [], RouteName.MATH)

        outcome = use_case.execute(self.request, self.policy())

        self.assertEqual(outcome.status, ExecutionStatus.ROUTE_NOT_SUPPORTED)
        self.assertEqual(outcome.result.status, ResultStatus.WITHHELD)
        self.assertEqual(outcome.result.degradations[0].kind, DegradationKind.CAPABILITY_UNAVAILABLE)
        self.assertEqual(
            outcome.result.degradations[0].disposition,
            DegradationDisposition.WITHHOLD,
        )
        self.assertEqual(runtime.requests, [])
        self.assertEqual(verifier.requests, [])
        self.assertEqual(planner.requested, [])

    def test_empty_generation_is_a_failed_result_without_content(self) -> None:
        use_case, _, verifier, _, _ = self.build(["   "], [])

        outcome = use_case.execute(self.request, self.policy())

        self.assertEqual(outcome.status, ExecutionStatus.ERROR)
        self.assertEqual(outcome.result.status, ResultStatus.FAILED)
        self.assertIsNone(outcome.result.content)
        self.assertEqual(outcome.result.failure.category, FailureCategory.PROVIDER_FAILURE)
        self.assertNotIn("CandidateGenerationError", outcome.result.reason)
        self.assertEqual(verifier.requests, [])


if __name__ == "__main__":
    unittest.main()
