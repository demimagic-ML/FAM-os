import unittest
from datetime import datetime, timezone

from fam_os.adapters.linux import build_privacy_reviewed_resource_state
from fam_os.adapters.linux.nvidia import NvidiaResourceReading
from fam_os.scheduler import (
    CpuProfile,
    GpuProfile,
    HardwareProfile,
    MemoryProfile,
    OperatingSystemProfile,
    StorageMedium,
    StorageProfile,
)


GIB = 1024**3
NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def hardware_profile() -> HardwareProfile:
    return HardwareProfile(
        1,
        NOW,
        "private-hostname",
        OperatingSystemProfile("Linux", "test-release", "x86_64"),
        CpuProfile("FAM Test CPU", 24),
        MemoryProfile(64 * GIB, 40 * GIB, 8 * GIB, 2 * GIB),
        StorageProfile(2_000 * GIB, 1_400 * GIB, 600 * GIB),
        (GpuProfile("FAM Test GPU", 16 * GIB, "600.1", "private-pci", 300.0),),
        ("/private/dev/accel0",),
    )


class PrivacyReviewedResourceDiscoveryTests(unittest.TestCase):
    def test_maps_complete_host_without_private_location_identifiers(self) -> None:
        reading = NvidiaResourceReading(0, "FAM Test GPU", 16 * GIB, 2 * GIB, 0.25, "600.1")
        state = build_privacy_reviewed_resource_state(
            hardware_profile(), (reading,), "inventory-live", "state-live"
        )

        self.assertEqual(len(state.inventory.cpu.logical_cpu_ids), 24)
        self.assertEqual(state.memory_current_bytes, 24 * GIB)
        self.assertEqual(state.swap_current_bytes, 6 * GIB)
        self.assertEqual(state.accelerators[0].current_memory_bytes, 2 * GIB)
        self.assertEqual(state.inventory.storage[0].medium, StorageMedium.NVME)
        self.assertIsNone(state.inventory.storage[0].mount_path)
        self.assertEqual(state.inventory.accelerators[0].device_id, "gpu-0")
        self.assertEqual(state.inventory.accelerators[1].device_id, "npu-0")

        rendered = repr(state)
        for private in ("private-hostname", "private-pci", "/private/dev/accel0"):
            self.assertNotIn(private, rendered)

    def test_requires_complete_live_memory_counters(self) -> None:
        incomplete = hardware_profile()
        incomplete = HardwareProfile(
            incomplete.schema_version,
            incomplete.captured_at,
            incomplete.hostname,
            incomplete.operating_system,
            incomplete.cpu,
            MemoryProfile(None, None, None, None),
            incomplete.storage,
        )
        with self.assertRaisesRegex(ValueError, "complete memory"):
            build_privacy_reviewed_resource_state(
                incomplete, (), "inventory-live", "state-live"
            )


if __name__ == "__main__":
    unittest.main()
