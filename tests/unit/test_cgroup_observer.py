import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.cgroup import CgroupV2Paths, CgroupV2ResourceObserver
from fam_os.supervisor import ResourceObservationError


FIXTURES = Path(__file__).parents[1] / "fixtures" / "cgroup"


class FakeLocator:
    def __init__(self, resource_group: str | None) -> None:
        self.resource_group = resource_group

    def control_group(self, service_id: str) -> str | None:
        return self.resource_group


class CgroupObserverTests(unittest.TestCase):
    def test_reads_memory_swap_cpu_io_events_and_pressure(self) -> None:
        observer = CgroupV2ResourceObserver(
            FakeLocator("/user.slice/fam-test.service"), CgroupV2Paths(FIXTURES)
        )
        snapshot = observer.observe("fam-test")

        self.assertEqual(snapshot.memory_current_bytes, 1_048_576)
        self.assertEqual(snapshot.memory_peak_bytes, 2_097_152)
        self.assertEqual(snapshot.memory_limit.maximum_bytes, 16_777_216)
        self.assertEqual(snapshot.swap_limit.maximum_bytes, 0)
        self.assertEqual(snapshot.cpu_usage_microseconds, 12_000)
        self.assertEqual(snapshot.cpu_user_microseconds, 8_000)
        self.assertEqual(snapshot.cpu_system_microseconds, 4_000)
        self.assertEqual(snapshot.io_read_bytes, 4_096)
        self.assertEqual(snapshot.io_write_bytes, 8_192)
        self.assertEqual(snapshot.io_read_operations, 3)
        self.assertEqual(snapshot.io_write_operations, 4)
        self.assertEqual(snapshot.cpu_quota.maximum_percent, 25.0)
        self.assertEqual(snapshot.tasks_current, 3)
        self.assertEqual(snapshot.tasks_limit.maximum, 8)
        self.assertEqual(snapshot.event_count("high"), 2)
        self.assertEqual(snapshot.pressure[0].total_stall_microseconds, 123)

    def test_missing_service_degrades_to_no_snapshot(self) -> None:
        observer = CgroupV2ResourceObserver(FakeLocator(None), CgroupV2Paths(FIXTURES))
        self.assertIsNone(observer.observe("fam-test"))

    def test_missing_group_degrades_to_no_snapshot(self) -> None:
        observer = CgroupV2ResourceObserver(
            FakeLocator("/missing.service"), CgroupV2Paths(FIXTURES)
        )
        self.assertIsNone(observer.observe("fam-test"))

    def test_invalid_controller_data_raises_stable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            group = Path(directory) / "fam-test.service"
            group.mkdir()
            (group / "memory.current").write_text("not-a-number")
            observer = CgroupV2ResourceObserver(
                FakeLocator("/fam-test.service"), CgroupV2Paths(Path(directory))
            )
            with self.assertRaisesRegex(ResourceObservationError, "invalid resource data"):
                observer.observe("fam-test")


if __name__ == "__main__":
    unittest.main()
