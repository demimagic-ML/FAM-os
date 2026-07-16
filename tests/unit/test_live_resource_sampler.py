import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fam_os.scheduler import (
    COMPAT_CPU_16GB_PROFILE_ID,
    LiveResourceSampler,
    ObservationStatus,
    ValidationProfilePurpose,
    ValidationProfileRef,
)
from fam_os.scheduler.live_ports import AcceleratorUsageReading, StorageCacheReading
from fam_os.supervisor import CpuQuotaCeiling, ResourceCeiling, ResourceEvent, ResourceSnapshot
from tests.contract.schema_configuration_fixtures import composed_configuration


START = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)


class FakeResources:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def observe(self, service_id):
        return self.snapshots.get(service_id)


class FakeAccelerators:
    def __init__(self, values):
        self.values = values

    def observe_accelerators(self):
        return self.values


class FakeStorage:
    def __init__(self, values):
        self.values = values

    def observe_storage(self):
        return self.values


class SequenceFactory:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def snapshot(service_id, *, memory, cpu, limit=None, quota=None, oom=0):
    return ResourceSnapshot(
        service_id,
        memory_current_bytes=memory,
        memory_peak_bytes=memory,
        memory_limit=None if limit is None else ResourceCeiling(limit),
        swap_current_bytes=0,
        swap_limit=ResourceCeiling(0),
        cpu_usage_microseconds=cpu,
        cpu_quota=None if quota is None else CpuQuotaCeiling(quota),
        events=(ResourceEvent("oom_kill", oom),),
    )


def sampler(*, snapshots=None, accelerators=True, storage=True, budget=None):
    budget = budget or composed_configuration().budget
    gpu_values = () if not accelerators else (
        AcceleratorUsageReading(budget.accelerators[0].device_id, 256, 0.25),
    )
    storage_values = () if not storage else (
        StorageCacheReading(budget.storage[0].storage_id, 512),
    )
    resources = FakeResources(snapshots or {})
    instance = LiveResourceSampler(
        budget, resources, FakeAccelerators(gpu_values), FakeStorage(storage_values),
        "fam.slice", ("fam-model",),
        SequenceFactory((START, START + timedelta(seconds=2), START + timedelta(seconds=4))),
        SequenceFactory(("observation-1", "observation-2", "observation-3")),
    )
    return instance, resources


class LiveResourceSamplerTests(unittest.TestCase):
    def test_repeated_scope_sample_computes_cpu_delta_without_double_counting_children(self):
        service, resources = sampler(snapshots={
            "fam.slice": snapshot("fam.slice", memory=1_000, cpu=1_000_000, quota=200),
            "fam-model": snapshot("fam-model", memory=800, cpu=700_000, oom=1),
        })
        first = service.sample()
        resources.snapshots["fam.slice"] = snapshot(
            "fam.slice", memory=1_200, cpu=1_500_000, quota=200
        )
        second = service.sample(first)

        self.assertEqual(first.status, ObservationStatus.BASELINE)
        self.assertEqual(second.status, ObservationStatus.COMPLETE)
        self.assertEqual(second.memory.current_bytes, 1_200)
        self.assertEqual(second.cpu.usage_delta_microseconds, 500_000)
        self.assertAlmostEqual(second.cpu.utilization_fraction, 0.125)
        self.assertEqual(first.managed_services[0].oom_kill_count, 1)

    def test_live_cgroup_ceiling_reduces_budget_and_preserves_bounded_reserve(self):
        budget = composed_configuration().budget
        limit = budget.memory.reserved_headroom_bytes + 1_024
        service, _ = sampler(budget=budget, snapshots={
            "fam.slice": snapshot("fam.slice", memory=512, cpu=1, limit=limit),
            "fam-model": snapshot("fam-model", memory=256, cpu=1),
        })
        point = service.sample()

        self.assertEqual(point.memory.effective_limit_bytes, limit)
        self.assertEqual(point.memory.scheduler_limit_bytes, 1_024)
        self.assertEqual(point.memory.reserved_headroom_bytes, budget.memory.reserved_headroom_bytes)

    def test_missing_scope_falls_back_to_known_children_and_is_degraded(self):
        service, _ = sampler(snapshots={
            "fam-model": snapshot("fam-model", memory=777, cpu=20),
        })
        point = service.sample()

        self.assertEqual(point.status, ObservationStatus.DEGRADED)
        self.assertEqual(point.memory.current_bytes, 777)
        self.assertEqual(point.memory.available_for_new_bytes, 0)
        self.assertIn("cgroup.scope_unavailable", point.reason_codes)
        self.assertIn("cgroup.scope_memory_fallback", point.reason_codes)

    def test_missing_accelerator_and_storage_are_explicit_not_free_capacity(self):
        service, _ = sampler(
            accelerators=False, storage=False,
            snapshots={
                "fam.slice": snapshot("fam.slice", memory=1, cpu=1),
                "fam-model": snapshot("fam-model", memory=1, cpu=1),
            },
        )
        point = service.sample()

        self.assertEqual(point.status, ObservationStatus.DEGRADED)
        self.assertIsNone(point.accelerators[0].available_for_new_bytes)
        self.assertIsNone(point.storage[0].available_cache_bytes)
        self.assertTrue(any(code.startswith("accelerator.unavailable:") for code in point.reason_codes))
        self.assertTrue(any(code.startswith("storage.unavailable:") for code in point.reason_codes))

    def test_compat_profile_keeps_visible_accelerator_disallowed(self):
        original = composed_configuration().budget
        gpu = replace(
            original.accelerators[0], placement_allowed=False,
            scheduler_memory_limit_bytes=0, current_memory_bytes=0,
        )
        budget = replace(
            original,
            validation_profile=ValidationProfileRef(
                COMPAT_CPU_16GB_PROFILE_ID,
                ValidationProfilePurpose.MINIMUM_COMPATIBILITY,
            ),
            accelerators=(gpu,),
        )
        service, _ = sampler(budget=budget, snapshots={
            "fam.slice": snapshot("fam.slice", memory=1, cpu=1),
            "fam-model": snapshot("fam-model", memory=1, cpu=1),
        })
        point = service.sample()

        self.assertFalse(point.accelerators[0].placement_allowed)
        self.assertEqual(point.accelerators[0].available_for_new_bytes, 0)

    def test_missing_policy_disabled_accelerator_does_not_degrade(self):
        original = composed_configuration().budget
        gpu = replace(
            original.accelerators[0], placement_allowed=False,
            scheduler_memory_limit_bytes=0, current_memory_bytes=0,
        )
        budget = replace(original, accelerators=(gpu,))
        service, _ = sampler(budget=budget, accelerators=False, snapshots={
            "fam.slice": snapshot("fam.slice", memory=1, cpu=1),
            "fam-model": snapshot("fam-model", memory=1, cpu=1),
        })

        point = service.sample()

        self.assertEqual(point.status, ObservationStatus.BASELINE)
        self.assertIsNone(point.accelerators[0].available_for_new_bytes)

    def test_previous_observation_must_match_scope_and_monotonic_time(self):
        service, _ = sampler(snapshots={
            "fam.slice": snapshot("fam.slice", memory=1, cpu=1),
            "fam-model": snapshot("fam-model", memory=1, cpu=1),
        })
        first = service.sample()
        with self.assertRaisesRegex(ValueError, "another resource scope"):
            service.sample(replace(first, scope_service_id="other.slice"))


if __name__ == "__main__":
    unittest.main()
