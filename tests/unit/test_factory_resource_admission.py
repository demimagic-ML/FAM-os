import unittest
from datetime import UTC, datetime

from fam_os.expert_factory import (
    TrainingResourceBudget,
    build_resource_snapshot,
    decide_training_admission,
)


NOW = datetime(2026, 7, 17, 23, 30, tzinfo=UTC)
GIB = 1024**3


class FactoryResourceAdmissionTests(unittest.TestCase):
    def test_idle_capacity_is_admitted(self):
        snapshot = _snapshot()
        decision = decide_training_admission(
            decision_id="admission-1", approval_id="approval-1",
            budget=_budget(), snapshot=snapshot, decided_at=NOW,
        )
        self.assertTrue(decision.admitted)
        self.assertEqual((), decision.reason_codes)

    def test_every_unsafe_live_condition_denies_before_worker_creation(self):
        snapshot = build_resource_snapshot(
            snapshot_id="snapshot-unsafe", logical_cpu_count=8,
            load_fraction=.9, available_ram_bytes=8 * GIB,
            free_disk_bytes=10 * GIB, gpu_total_bytes=16 * GIB,
            gpu_used_bytes=8 * GIB, gpu_utilization_fraction=.8,
            gpu_temperature_celsius=81, inference_conflict=True, observed_at=NOW,
        )
        decision = decide_training_admission(
            decision_id="admission-unsafe", approval_id="approval-1",
            budget=_budget(), snapshot=snapshot, decided_at=NOW,
        )
        self.assertFalse(decision.admitted)
        self.assertEqual({
            "resource.cpu_foreground_pressure", "resource.cpu_insufficient",
            "resource.disk_insufficient", "resource.gpu_foreground_pressure",
            "resource.inference_conflict", "resource.ram_insufficient",
            "resource.thermal_headroom_insufficient", "resource.vram_insufficient",
        }, set(decision.reason_codes))


def _snapshot():
    return build_resource_snapshot(
        snapshot_id="snapshot-1", logical_cpu_count=24, load_fraction=.1,
        available_ram_bytes=48 * GIB, free_disk_bytes=400 * GIB,
        gpu_total_bytes=16 * GIB, gpu_used_bytes=GIB,
        gpu_utilization_fraction=.05, gpu_temperature_celsius=44,
        inference_conflict=False, observed_at=NOW,
    )


def _budget():
    return TrainingResourceBudget(
        "budget-1", 16, 40 * GIB, 14 * GIB, 200 * GIB, 82,
        10_000_000, "workers.full.v1",
    )


if __name__ == "__main__":
    unittest.main()
