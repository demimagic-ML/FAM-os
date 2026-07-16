import unittest

from fam_os.experts import ExpertDescriptor, ExpertTier
from fam_os.scheduler import PlacementPlan, ResourceBudget


class ExpertContractTests(unittest.TestCase):
    def test_describes_economical_code_expert(self) -> None:
        expert = ExpertDescriptor(
            expert_id="code-qwen-7b",
            model_ref="qwen2.5-coder:7b",
            tier=ExpertTier.ECONOMICAL,
            capabilities=("code",),
            max_context_tokens=2048,
            estimated_resident_bytes=6_700_000_000,
            verifier_ids=("python-tests-v1",),
        )
        self.assertEqual(expert.tier, ExpertTier.ECONOMICAL)

    def test_live_descriptor_uses_manifest_capability_namespace(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown expert capability domain"):
            ExpertDescriptor(
                expert_id="invalid-capability",
                model_ref="local-model",
                tier=ExpertTier.MICRO,
                capabilities=("typo.route",),
                max_context_tokens=128,
                estimated_resident_bytes=1,
            )


class SchedulerContractTests(unittest.TestCase):
    def test_represents_cpu_only_sixteen_gib_budget(self) -> None:
        budget = ResourceBudget(16 * 1024**3, 0, 2048)
        self.assertFalse(budget.gpu_allowed)
        self.assertEqual(budget.context_tokens, 2048)

    def test_plan_cannot_evict_activated_expert(self) -> None:
        budget = ResourceBudget(16 * 1024**3, 0, 2048)
        with self.assertRaisesRegex(ValueError, "being activated"):
            PlacementPlan("code-qwen-14b", budget, ("code-qwen-14b",))


if __name__ == "__main__":
    unittest.main()
