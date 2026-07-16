import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fam_os.scheduler import (
    COMPAT_CPU_16GB_PROFILE_ID,
    CONFIGURATION_CONTRACT_VERSION,
    AcceleratorKind,
    AcceleratorRuntimeState,
    ConfigurationCompositionRequest,
    ConfigurationDecisionKind,
    DiscoveredResourceState,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    HostAcceleratorInventory,
    HostCpuInventory,
    HostInventory,
    HostMemoryInventory,
    HostStorageInventory,
    PressureReading,
    ResourcePolicy,
    ResourceRestriction,
    SchedulerDefaults,
    SessionResourceOverride,
    StorageMedium,
    StorageRuntimeState,
    UserResourcePolicy,
    ValidationProfileConfiguration,
    ValidationProfilePurpose,
    ValidationProfileRef,
    compose_resource_configuration,
)


GIB = 1024**3
NOW = datetime(2026, 7, 16, 14, 0, tzinfo=UTC)


def policy(*, accelerator_allowed: bool = False, reserved_cpus: int = 2) -> ResourcePolicy:
    return ResourcePolicy(
        cpu_quota_fraction=1.0,
        reserved_logical_cpu_count=reserved_cpus,
        memory_limit_fraction=1.0,
        memory_headroom_bytes=8 * GIB,
        max_swap_bytes=0,
        accelerator_allowed=accelerator_allowed,
        accelerator_memory_fraction=0.9 if accelerator_allowed else 0.0,
        accelerator_reserved_memory_bytes=2 * GIB,
        storage_cache_fraction=0.8,
        storage_reserved_free_bytes=100 * GIB,
    )


def inventory() -> HostInventory:
    return HostInventory(
        "inventory-full",
        NOW,
        "linux",
        "test",
        HostCpuInventory("x86_64", tuple(range(24)), "CPU", 24),
        HostMemoryInventory(64 * GIB, 40 * GIB),
        (HostStorageInventory("nvme", StorageMedium.NVME, 2_000 * GIB, 500 * GIB, True, "/"),),
        (HostAcceleratorInventory("gpu-0", AcceleratorKind.GPU, "GPU", 16 * GIB),),
    )


def discovery(**overrides: object) -> DiscoveredResourceState:
    values = {
        "state_id": "discovery-1",
        "captured_at": NOW,
        "inventory": inventory(),
        "memory_current_bytes": 12 * GIB,
        "swap_limit_bytes": 0,
        "swap_current_bytes": 0,
        "cgroup_cpu_quota_cores": 20.0,
        "cgroup_memory_limit_bytes": 48 * GIB,
        "accelerators": (AcceleratorRuntimeState("gpu-0", 4 * GIB),),
        "storage": (StorageRuntimeState("nvme", 20 * GIB),),
        "pressure": (
            PressureReading("cpu", NOW, utilization_fraction=0.25),
            PressureReading("memory", NOW, stall_fraction=0.01),
        ),
    }
    values.update(overrides)
    return DiscoveredResourceState(**values)


def defaults() -> SchedulerDefaults:
    return SchedulerDefaults(
        "defaults-1",
        ValidationProfileRef("safe-default", ValidationProfilePurpose.CUSTOM),
        replace(policy(), max_memory_bytes=16 * GIB, max_cpu_cores=8.0),
    )


def full_profile() -> ValidationProfileConfiguration:
    return ValidationProfileConfiguration(
        "profile-full-1",
        ValidationProfileRef(
            FULL_REFERENCE_WORKSTATION_PROFILE_ID,
            ValidationProfilePurpose.FULL_HOST_CAPABILITY,
        ),
        policy(accelerator_allowed=True),
    )


def request(**overrides: object) -> ConfigurationCompositionRequest:
    values = {
        "composition_id": "composition-1",
        "defaults": defaults(),
        "discovery": discovery(),
        "profile": full_profile(),
    }
    values.update(overrides)
    return ConfigurationCompositionRequest(**values)


class ConfigurationLayeringTests(unittest.TestCase):
    def test_trusted_profile_replaces_defaults_but_discovery_clamps_it(self) -> None:
        result = compose_resource_configuration(request())
        self.assertEqual(20.0, result.budget.cpu.scheduler_quota_cores)
        self.assertEqual(40 * GIB, result.budget.memory.scheduler_limit_bytes)
        self.assertTrue(result.budget.accelerators[0].placement_allowed)
        self.assertEqual(14 * GIB, result.budget.accelerators[0].scheduler_memory_limit_bytes)
        self.assertEqual(400 * GIB, result.budget.storage[0].scheduler_cache_limit_bytes)
        self.assertIn(ConfigurationDecisionKind.CLAMPED, {item.kind for item in result.decisions})

    def test_user_policy_can_only_restrict_selected_profile(self) -> None:
        user = UserResourcePolicy(
            "user-policy-1",
            ResourceRestriction(
                max_cpu_cores=12,
                max_memory_bytes=32 * GIB,
                accelerator_allowed=False,
                max_storage_cache_bytes=100 * GIB,
            ),
        )
        result = compose_resource_configuration(request(user_policy=user))
        self.assertEqual(12, result.budget.cpu.scheduler_quota_cores)
        self.assertEqual(32 * GIB, result.budget.memory.scheduler_limit_bytes)
        self.assertFalse(result.budget.accelerators[0].placement_allowed)
        self.assertEqual(100 * GIB, result.budget.storage[0].scheduler_cache_limit_bytes)

    def test_session_override_further_restricts_user_policy(self) -> None:
        user = UserResourcePolicy("user-1", ResourceRestriction(max_cpu_cores=12))
        session = SessionResourceOverride(
            "session-limit-1",
            "session-1",
            NOW - timedelta(minutes=1),
            ResourceRestriction(max_cpu_cores=8, minimum_memory_headroom_bytes=16 * GIB),
            NOW + timedelta(hours=1),
        )
        result = compose_resource_configuration(
            request(user_policy=user, session_override=session)
        )
        self.assertEqual(8, result.budget.cpu.scheduler_quota_cores)
        self.assertEqual(16 * GIB, result.budget.memory.reserved_headroom_bytes)
        self.assertEqual(32 * GIB, result.budget.memory.scheduler_limit_bytes)

    def test_expired_session_override_is_ignored_and_audited(self) -> None:
        session = SessionResourceOverride(
            "expired-1",
            "session-1",
            NOW - timedelta(hours=2),
            ResourceRestriction(max_cpu_cores=2),
            NOW - timedelta(hours=1),
        )
        result = compose_resource_configuration(request(session_override=session))
        self.assertEqual(20, result.budget.cpu.scheduler_quota_cores)
        self.assertIn("session_override_inactive", {item.reason_code for item in result.decisions})

    def test_restriction_cannot_enable_accelerator_disabled_by_defaults(self) -> None:
        user = UserResourcePolicy("user-1", ResourceRestriction(accelerator_allowed=True))
        result = compose_resource_configuration(request(profile=None, user_policy=user))
        self.assertFalse(result.budget.accelerators[0].placement_allowed)

    def test_ssd_capacity_is_not_combined_with_memory(self) -> None:
        result = compose_resource_configuration(request())
        self.assertEqual(48 * GIB, result.budget.memory.effective_limit_bytes)
        self.assertEqual(500 * GIB, result.budget.storage[0].effective_cache_limit_bytes)

    def test_over_budget_current_memory_remains_visible(self) -> None:
        state = discovery(memory_current_bytes=50 * GIB)
        result = compose_resource_configuration(request(discovery=state))
        self.assertEqual(50 * GIB, result.budget.memory.current_bytes)
        self.assertEqual(0, result.budget.memory.available_for_new_bytes)

    def test_composition_is_deterministic_for_identical_inputs(self) -> None:
        self.assertEqual(
            compose_resource_configuration(request()),
            compose_resource_configuration(request()),
        )

    def test_cpu_reserve_must_leave_schedulable_capacity(self) -> None:
        invalid = replace(full_profile(), policy=policy(accelerator_allowed=True, reserved_cpus=24))
        with self.assertRaisesRegex(ValueError, "leave at least one"):
            compose_resource_configuration(request(profile=invalid))

    def test_discovery_rejects_runtime_resource_outside_inventory(self) -> None:
        with self.assertRaisesRegex(ValueError, "must exist in inventory"):
            discovery(accelerators=(AcceleratorRuntimeState("gpu-missing", 0),))


class ConfigurationContractTests(unittest.TestCase):
    def test_configuration_roots_require_current_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_version"):
            replace(defaults(), contract_version="fam.configuration/v2")
        self.assertEqual(CONFIGURATION_CONTRACT_VERSION, defaults().contract_version)

    def test_restriction_requires_at_least_one_constraint(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            ResourceRestriction()

    def test_policy_rejects_invalid_fraction(self) -> None:
        with self.assertRaisesRegex(ValueError, "fraction"):
            replace(policy(), cpu_quota_fraction=1.1)

    def test_compatibility_profile_cannot_enable_acceleration(self) -> None:
        profile = ValidationProfileRef(
            COMPAT_CPU_16GB_PROFILE_ID,
            ValidationProfilePurpose.MINIMUM_COMPATIBILITY,
        )
        with self.assertRaisesRegex(ValueError, "cannot allow acceleration"):
            ValidationProfileConfiguration(
                "invalid-compat",
                profile,
                policy(accelerator_allowed=True),
            )

    def test_session_expiry_must_follow_issue_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "follow issued_at"):
            SessionResourceOverride(
                "session-1",
                "session-1",
                NOW,
                ResourceRestriction(max_cpu_cores=4),
                NOW,
            )


if __name__ == "__main__":
    unittest.main()
