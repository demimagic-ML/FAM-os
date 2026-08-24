import tempfile
import unittest
from pathlib import Path

from fam_os.adaptation.resource_policy import OperatingState
from fam_os.adapters.linux.nvidia import NVIDIA_RESOURCE_QUERY
from fam_os.adapters.linux.operating_state import OperatingStateObservation
from fam_os.product.composition.live_capacity import ProductCapacityObserver
from fam_os.product.composition.validation_profiles import load_validation_profile
from fam_os.scheduler import (
    COMPAT_CPU_16GB_PROFILE_ID,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
)
from fam_os.supervisor import ResourceCeiling, ResourceSnapshot


GIB = 1024**3


class ProductLiveCapacityTests(unittest.TestCase):
    def test_full_host_reserves_os_and_vram_and_applies_cgroup_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            _write_meminfo(meminfo, 64, 40)
            observer = ProductCapacityObserver(
                meminfo,
                _Runner({NVIDIA_RESOURCE_QUERY: "0, GPU, 16384, 2048, 10, 600.1"}),
                _Operating(OperatingState(None, None, 60, 0.1, 600)),
                lambda: ResourceSnapshot(
                    "fam-ollama", memory_current_bytes=5 * GIB,
                    memory_limit=ResourceCeiling(20 * GIB),
                ),
            )

            capacity = observer.observe()

            self.assertEqual(12 * GIB, capacity.reserved_host_bytes)
            self.assertEqual(GIB, capacity.reserved_vram_bytes)
            self.assertEqual(15 * GIB, capacity.host_allocation_ceiling_bytes)
            self.assertEqual(15 * GIB, capacity.schedulable_host_bytes)
            self.assertEqual(13 * GIB, capacity.schedulable_vram_bytes)
            self.assertTrue(capacity.background_adaptation_allowed)
            self.assertIn("cgroup.managed_ceiling_applied", capacity.reason_codes)

    def test_missing_managed_snapshot_denies_new_host_allocation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            _write_meminfo(meminfo, 16, 12)
            capacity = ProductCapacityObserver(
                meminfo, _Runner({}),
                _Operating(OperatingState(None, None, 60, 0.1, 0)),
                lambda: None,
            ).observe()

            self.assertEqual(0, capacity.schedulable_host_bytes)
            self.assertIn(
                "cgroup.managed_snapshot_unavailable", capacity.reason_codes,
            )

    def test_thermal_policy_caps_generation_and_blocks_prefetch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            _write_meminfo(meminfo, 64, 40)
            capacity = ProductCapacityObserver(
                meminfo, _Runner({}),
                _Operating(OperatingState(None, None, 90, 0.1, 600)),
            ).observe()

            self.assertEqual("micro", capacity.maximum_expert_tier)
            self.assertFalse(capacity.speculative_prefetch_allowed)
            self.assertFalse(capacity.background_adaptation_allowed)
            self.assertIn("thermal.protect", capacity.reason_codes)

    def test_unknown_system_battery_blocks_speculative_background_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            _write_meminfo(meminfo, 64, 40)
            capacity = ProductCapacityObserver(
                meminfo, _Runner({}),
                _Operating(
                    OperatingState(None, None, 60, 0.1, 600),
                    ("battery.reading_unavailable",),
                ),
            ).observe()

            self.assertFalse(capacity.speculative_prefetch_allowed)
            self.assertFalse(capacity.background_adaptation_allowed)

    def test_explicit_compat_profile_denies_gpu_and_caps_scheduler_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            _write_meminfo(meminfo, 64, 40)
            runner = _Runner({
                NVIDIA_RESOURCE_QUERY: "0, GPU, 16384, 0, 10, 600.1",
            })
            capacity = ProductCapacityObserver(
                meminfo, runner,
                _Operating(OperatingState(None, None, 60, 0.1, 600)),
                lambda: ResourceSnapshot(
                    "fam-ollama", memory_current_bytes=0,
                    memory_limit=ResourceCeiling(16 * GIB),
                ),
                validation_profile=load_validation_profile(
                    COMPAT_CPU_16GB_PROFILE_ID,
                ),
            ).observe()

            self.assertNotIn(NVIDIA_RESOURCE_QUERY, runner.commands)
            self.assertEqual(2 * GIB, capacity.reserved_host_bytes)
            self.assertEqual(14 * GIB, capacity.schedulable_host_bytes)
            self.assertEqual(0, capacity.schedulable_vram_bytes)
            self.assertIn("profile.compat-cpu-16gb", capacity.reason_codes)
            self.assertIn("accelerator.visibility.denied", capacity.reason_codes)

    def test_explicit_full_profile_applies_vram_fraction_and_reserve(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            meminfo = Path(temporary) / "meminfo"
            _write_meminfo(meminfo, 64, 40)
            runner = _Runner({
                NVIDIA_RESOURCE_QUERY: "0, GPU, 16384, 0, 10, 600.1",
            })
            capacity = ProductCapacityObserver(
                meminfo, runner,
                _Operating(OperatingState(None, None, 60, 0.1, 600)),
                validation_profile=load_validation_profile(
                    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
                ),
            ).observe()

            self.assertIn(NVIDIA_RESOURCE_QUERY, runner.commands)
            self.assertEqual(12 * GIB, capacity.reserved_host_bytes)
            self.assertEqual(14 * GIB, capacity.schedulable_vram_bytes)
            self.assertIn(
                "profile.full-reference-workstation", capacity.reason_codes,
            )


class _Runner:
    def __init__(self, outputs):
        self.outputs = outputs
        self.commands = []

    def run(self, command, timeout_seconds=10.0):
        del timeout_seconds
        self.commands.append(command)
        return self.outputs.get(command)


class _Operating:
    def __init__(self, state, reasons=()):
        self.state = state
        self.reasons = reasons

    def observe(self):
        return OperatingStateObservation(self.state, self.reasons)


def _write_meminfo(path: Path, total_gib: int, available_gib: int) -> None:
    path.write_text(
        f"MemTotal: {total_gib * GIB // 1024} kB\n"
        f"MemAvailable: {available_gib * GIB // 1024} kB\n",
    )


if __name__ == "__main__":
    unittest.main()
