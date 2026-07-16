import unittest
from dataclasses import replace

from fam_os.experts import (
    ExpertCompatibilityEvaluator,
    ExpertCompatibilityStatus,
    ExpertResourceRequirements,
)
from fam_os.scheduler.resources import (
    COMPAT_CPU_16GB_PROFILE_ID,
    AcceleratorResourceBudget,
    MemoryResourceBudget,
    ValidationProfilePurpose,
    ValidationProfileRef,
)
from tests.contract.schema_manifest_fixtures import (
    GIB,
    effective_budget,
    expert_manifest,
    host_inventory,
)


class ExpertHardwareCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = ExpertCompatibilityEvaluator()
        self.inventory = host_inventory()
        self.budget = effective_budget()

    def test_full_profile_is_compatible_and_names_current_resources(self) -> None:
        report = self.evaluator.evaluate(expert_manifest(), self.inventory, self.budget)
        self.assertEqual(ExpertCompatibilityStatus.COMPATIBLE, report.status)
        self.assertEqual(("nvme-root",), report.compatible_storage_ids)
        self.assertEqual(4 * GIB, report.required_system_memory_bytes)
        self.assertEqual((), report.reason_codes)

    def test_optional_acceleration_degrades_to_cpu_under_compat_profile(self) -> None:
        manifest = replace(
            expert_manifest(),
            resources=ExpertResourceRequirements(
                2 * GIB,
                2 * GIB,
                8192,
                4 * GIB,
                8 * GIB,
                True,
                ("x86_64",),
            ),
        )
        report = self.evaluator.evaluate(manifest, self.inventory, self.compat_budget())
        self.assertEqual(ExpertCompatibilityStatus.COMPATIBLE_CPU_ONLY, report.status)
        self.assertIn("degradation.optional_accelerator_unavailable", report.reason_codes)

    def test_required_accelerator_is_profile_incompatible_or_currently_busy(self) -> None:
        manifest = replace(
            expert_manifest(),
            resources=ExpertResourceRequirements(
                2 * GIB,
                2 * GIB,
                8192,
                4 * GIB,
                8 * GIB,
                False,
                ("x86_64",),
            ),
        )
        blocked = self.evaluator.evaluate(manifest, self.inventory, self.compat_budget())
        self.assertEqual(ExpertCompatibilityStatus.INCOMPATIBLE, blocked.status)
        self.assertIn("profile.required_accelerator_unavailable", blocked.reason_codes)

        gpu = replace(self.budget.accelerators[0], current_memory_bytes=8 * GIB)
        busy_budget = replace(self.budget, accelerators=(gpu,))
        busy = self.evaluator.evaluate(manifest, self.inventory, busy_budget)
        self.assertEqual(ExpertCompatibilityStatus.CURRENTLY_CONSTRAINED, busy.status)
        self.assertIn("current.required_accelerator_busy", busy.reason_codes)

    def test_architecture_physical_memory_storage_and_current_memory_are_distinct(self) -> None:
        cases = (
            (
                ExpertResourceRequirements(2 * GIB, 2 * GIB, 8192, supported_architectures=("aarch64",)),
                "hardware.cpu_architecture_unsupported",
                ExpertCompatibilityStatus.INCOMPATIBLE,
            ),
            (
                ExpertResourceRequirements(70 * GIB, 2 * GIB, 8192),
                "hardware.system_memory_insufficient",
                ExpertCompatibilityStatus.INCOMPATIBLE,
            ),
            (
                ExpertResourceRequirements(2 * GIB, 3000 * GIB, 8192),
                "hardware.storage_capacity_insufficient",
                ExpertCompatibilityStatus.INCOMPATIBLE,
            ),
        )
        for resources, reason, status in cases:
            with self.subTest(reason=reason):
                report = self.evaluator.evaluate(
                    replace(expert_manifest(), resources=resources),
                    self.inventory,
                    self.budget,
                )
                self.assertEqual(status, report.status)
                self.assertIn(reason, report.reason_codes)

        memory = replace(self.budget.memory, current_bytes=50 * GIB)
        constrained = self.evaluator.evaluate(
            expert_manifest(), self.inventory, replace(self.budget, memory=memory)
        )
        self.assertEqual(ExpertCompatibilityStatus.CURRENTLY_CONSTRAINED, constrained.status)
        self.assertIn("current.system_memory_busy", constrained.reason_codes)

    def test_rejects_budget_from_another_inventory(self) -> None:
        with self.assertRaisesRegex(ValueError, "another inventory"):
            self.evaluator.evaluate(
                expert_manifest(),
                self.inventory,
                replace(self.budget, inventory_id="other"),
            )

    def compat_budget(self):
        profile = ValidationProfileRef(
            COMPAT_CPU_16GB_PROFILE_ID,
            ValidationProfilePurpose.MINIMUM_COMPATIBILITY,
        )
        memory = MemoryResourceBudget(16 * GIB, 14 * GIB, 2 * GIB, 0, 0, 0)
        gpu = AcceleratorResourceBudget("gpu-0", False, 15 * GIB, 0, 15 * GIB, 0)
        return replace(
            self.budget,
            budget_id="budget-compat",
            validation_profile=profile,
            memory=memory,
            accelerators=(gpu,),
        )


if __name__ == "__main__":
    unittest.main()
