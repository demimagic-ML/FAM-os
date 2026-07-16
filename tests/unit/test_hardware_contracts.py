import unittest
from datetime import datetime, timezone

from fam_os.scheduler import (
    CpuProfile,
    HardwareProfile,
    MemoryProfile,
    OperatingSystemProfile,
    RuntimeVersion,
    StorageProfile,
)


def _profile(**overrides: object) -> HardwareProfile:
    values = {
        "schema_version": 1,
        "captured_at": datetime(2026, 7, 16, tzinfo=timezone.utc),
        "hostname": "fam-test-host",
        "operating_system": OperatingSystemProfile("Linux", "test", "x86_64"),
        "cpu": CpuProfile("FAM Test CPU", 2),
        "memory": MemoryProfile(16 * 1024**3, 8 * 1024**3, 0, 0),
        "storage": StorageProfile(2_000, 500, 1_500),
        "runtimes": (RuntimeVersion("ollama", "ollama version test"),),
    }
    values.update(overrides)
    return HardwareProfile(**values)


class HardwareProfileTests(unittest.TestCase):
    def test_finds_runtime_version(self) -> None:
        self.assertEqual(_profile().runtime_version("ollama"), "ollama version test")

    def test_requires_timezone_aware_capture_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            _profile(captured_at=datetime(2026, 7, 16))

    def test_rejects_negative_memory(self) -> None:
        with self.assertRaisesRegex(ValueError, "memory"):
            MemoryProfile(-1, None, None, None)


if __name__ == "__main__":
    unittest.main()

