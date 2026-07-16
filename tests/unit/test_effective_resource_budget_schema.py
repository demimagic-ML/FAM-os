import unittest
from datetime import datetime, timezone

from fam_os.scheduler import (
    COMPAT_CPU_16GB_PROFILE_ID,
    EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    AcceleratorResourceBudget,
    CpuResourceBudget,
    EffectiveResourceBudget,
    MemoryResourceBudget,
    PressureReading,
    StorageResourceBudget,
    ValidationProfilePurpose,
    ValidationProfileRef,
)


GIB = 1024**3
CAPTURED_AT = datetime(2026, 7, 16, 12, 5, tzinfo=timezone.utc)
GPU_ID = "gpu:0000:01:00.0"
STORAGE_ID = "storage:root"


def _cpu() -> CpuResourceBudget:
    return CpuResourceBudget(
        visible_logical_cpu_ids=tuple(range(24)),
        schedulable_logical_cpu_ids=tuple(range(22)),
        reserved_logical_cpu_ids=(22, 23),
        scheduler_quota_cores=22.0,
        cgroup_quota_cores=24.0,
        current_utilization_fraction=0.25,
    )


def _memory() -> MemoryResourceBudget:
    return MemoryResourceBudget(
        effective_limit_bytes=64 * GIB,
        scheduler_limit_bytes=48 * GIB,
        reserved_headroom_bytes=16 * GIB,
        current_bytes=12 * GIB,
        cgroup_limit_bytes=64 * GIB,
        swap_limit_bytes=0,
        swap_current_bytes=0,
    )


def _accelerator(allowed: bool = True) -> AcceleratorResourceBudget:
    return AcceleratorResourceBudget(
        device_id=GPU_ID,
        placement_allowed=allowed,
        effective_memory_limit_bytes=16 * GIB,
        scheduler_memory_limit_bytes=14 * GIB if allowed else 0,
        reserved_memory_bytes=2 * GIB,
        current_memory_bytes=4 * GIB if allowed else 0,
    )


def _storage() -> StorageResourceBudget:
    return StorageResourceBudget(
        storage_id=STORAGE_ID,
        effective_cache_limit_bytes=500 * GIB,
        scheduler_cache_limit_bytes=400 * GIB,
        reserved_free_bytes=100 * GIB,
        current_cache_bytes=40 * GIB,
        read_limit_bytes_per_second=2_000_000_000,
        write_limit_bytes_per_second=1_000_000_000,
    )


def _full_budget(**overrides: object) -> EffectiveResourceBudget:
    values = {
        "budget_id": "budget-full-001",
        "inventory_id": "reference-workstation-20260716",
        "captured_at": CAPTURED_AT,
        "validation_profile": ValidationProfileRef(
            FULL_REFERENCE_WORKSTATION_PROFILE_ID,
            ValidationProfilePurpose.FULL_HOST_CAPABILITY,
        ),
        "cpu": _cpu(),
        "memory": _memory(),
        "accelerators": (_accelerator(),),
        "storage": (_storage(),),
        "pressure": (
            PressureReading("cpu", CAPTURED_AT, utilization_fraction=0.25),
            PressureReading("memory", CAPTURED_AT, stall_fraction=0.01),
            PressureReading(GPU_ID, CAPTURED_AT, utilization_fraction=0.30),
            PressureReading(STORAGE_ID, CAPTURED_AT, stall_fraction=0.02),
        ),
    }
    values.update(overrides)
    return EffectiveResourceBudget(**values)


class ValidationProfileIdentityTests(unittest.TestCase):
    def test_reserved_profiles_require_their_declared_purpose(self) -> None:
        with self.assertRaisesRegex(ValueError, "minimum_compatibility"):
            ValidationProfileRef(
                COMPAT_CPU_16GB_PROFILE_ID,
                ValidationProfilePurpose.FULL_HOST_CAPABILITY,
            )

    def test_custom_profiles_use_custom_purpose(self) -> None:
        custom = ValidationProfileRef("quiet-laptop", ValidationProfilePurpose.CUSTOM)
        self.assertEqual(custom.profile_id, "quiet-laptop")


class EffectiveResourceBudgetSchemaTests(unittest.TestCase):
    def test_represents_cpu_ram_vram_ssd_and_current_pressure(self) -> None:
        budget = _full_budget()
        self.assertEqual(
            budget.contract_version,
            EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION,
        )
        self.assertEqual(len(budget.cpu.visible_logical_cpu_ids), 24)
        self.assertTrue(budget.accelerators[0].placement_allowed)
        self.assertEqual(budget.memory.available_for_new_bytes, 36 * GIB)
        self.assertEqual(budget.storage[0].read_limit_bytes_per_second, 2_000_000_000)

    def test_cpu_allocation_must_stay_inside_visible_set(self) -> None:
        with self.assertRaisesRegex(ValueError, "disjoint visible CPUs"):
            CpuResourceBudget((0, 1), (0, 2), (1,), 1.0, 0.1)

    def test_scheduler_cpu_quota_cannot_exceed_cgroup_quota(self) -> None:
        with self.assertRaisesRegex(ValueError, "cgroup quota"):
            CpuResourceBudget((0, 1), (0, 1), (), 2.0, 0.1, cgroup_quota_cores=1.5)

    def test_memory_headroom_is_inside_effective_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "headroom"):
            MemoryResourceBudget(16 * GIB, 15 * GIB, 2 * GIB, 1, 0, 0)

    def test_current_over_budget_remains_representable(self) -> None:
        memory = MemoryResourceBudget(16 * GIB, 12 * GIB, 4 * GIB, 13 * GIB, 0, 0)
        self.assertEqual(memory.available_for_new_bytes, 0)

    def test_accelerator_reserve_cannot_be_reported_as_schedulable_vram(self) -> None:
        with self.assertRaisesRegex(ValueError, "reserve"):
            AcceleratorResourceBudget(GPU_ID, True, 16 * GIB, 15 * GIB, 2 * GIB, 0)

    def test_disallowed_accelerator_has_zero_scheduler_memory(self) -> None:
        with self.assertRaisesRegex(ValueError, "zero scheduler memory"):
            AcceleratorResourceBudget(GPU_ID, False, 16 * GIB, 1, 0, 0)

    def test_compat_profile_cannot_enable_gpu_placement(self) -> None:
        profile = ValidationProfileRef(
            COMPAT_CPU_16GB_PROFILE_ID,
            ValidationProfilePurpose.MINIMUM_COMPATIBILITY,
        )
        with self.assertRaisesRegex(ValueError, "cannot allow accelerator"):
            _full_budget(validation_profile=profile)

    def test_compat_profile_can_record_visible_but_disallowed_gpu(self) -> None:
        profile = ValidationProfileRef(
            COMPAT_CPU_16GB_PROFILE_ID,
            ValidationProfilePurpose.MINIMUM_COMPATIBILITY,
        )
        budget = _full_budget(validation_profile=profile, accelerators=(_accelerator(False),))
        self.assertFalse(budget.accelerators[0].placement_allowed)

    def test_pressure_must_reference_a_budgeted_resource(self) -> None:
        pressure = (PressureReading("gpu:missing", CAPTURED_AT, utilization_fraction=0.1),)
        with self.assertRaisesRegex(ValueError, "unknown resources"):
            _full_budget(pressure=pressure)

    def test_pressure_values_are_normalized(self) -> None:
        with self.assertRaisesRegex(ValueError, "between zero and one"):
            PressureReading("cpu", CAPTURED_AT, utilization_fraction=1.1)

    def test_requires_supported_contract_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_version"):
            _full_budget(contract_version="fam.hardware.budget/v2")


if __name__ == "__main__":
    unittest.main()
