import unittest

from fam_os.core.execution.attempt import AttemptExecutor
from fam_os.core.execution.placement import PlacementExecutionError, PlacementExecutor
from fam_os.core.execution.policy import GenerationSettings
from fam_os.core.execution.prompts import repair_messages
from fam_os.experts import ExpertTier
from fam_os.verification import (
    VerificationEvidence,
    VerificationReport,
    VerificationStatus,
)

from tests.unit.execution_fakes import (
    FakeCatalog,
    FakePlanner,
    FakeRuntime,
    FakeVerifier,
    expert,
    plan,
)


class RepairPromptTests(unittest.TestCase):
    def test_uses_bounded_verifier_feedback_and_preserves_requirements(self) -> None:
        report = VerificationReport(
            "attempt-1",
            "tests",
            VerificationStatus.FAILED,
            "tests",
            "failed",
            0.1,
            VerificationEvidence(stderr="x" * 4_500),
        )
        messages = repair_messages("original", "candidate", report, "keep API")
        prompt = messages[1].content
        self.assertNotIn("x" * 4_001, prompt)
        self.assertIn("x" * 4_000, prompt)
        self.assertIn("without weakening any requirement", prompt)
        self.assertIn("keep API", prompt)


class PlacementExecutorTests(unittest.TestCase):
    def test_resolves_every_eviction_before_unloading_any_model(self) -> None:
        active = expert("active", "active:model", ExpertTier.ECONOMICAL)
        known = expert("known", "known:model", ExpertTier.MICRO)
        runtime = FakeRuntime([])
        catalog = FakeCatalog((active, known))
        planner = FakePlanner((plan("active", ("known", "missing")),))
        executor = PlacementExecutor(runtime, catalog, planner)

        with self.assertRaisesRegex(PlacementExecutionError, "unknown expert"):
            executor.prepare(active)

        self.assertEqual(runtime.unloaded, [])

    def test_scheduler_context_becomes_inference_context(self) -> None:
        active = expert("active", "active:model", ExpertTier.ECONOMICAL)
        placement = plan("active", context_tokens=3_000)
        runtime = FakeRuntime(["candidate"])
        verifier = FakeVerifier([VerificationStatus.PASSED])
        attempts = AttemptExecutor(runtime, verifier)

        from fam_os.core.execution.contracts import AttemptKind
        from fam_os.core.execution.prompts import expert_messages

        attempts.execute(
            "request-1:1",
            AttemptKind.ECONOMICAL,
            active,
            placement,
            expert_messages("build it"),
            GenerationSettings(512),
        )

        self.assertEqual(runtime.requests[0].context_tokens, 3_000)
        self.assertEqual(runtime.requests[0].max_output_tokens, 512)


if __name__ == "__main__":
    unittest.main()
