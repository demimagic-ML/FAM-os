import unittest
from datetime import datetime, timezone

from fam_os.scheduler import (
    HOST_INVENTORY_CONTRACT_VERSION,
    AcceleratorKind,
    HostAcceleratorInventory,
    HostCpuInventory,
    HostInventory,
    HostMemoryInventory,
    HostStorageInventory,
    StorageMedium,
)


CAPTURED_AT = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


def _inventory(**overrides: object) -> HostInventory:
    values = {
        "inventory_id": "reference-workstation-20260716",
        "captured_at": CAPTURED_AT,
        "operating_system": "Linux",
        "os_release": "test",
        "cpu": HostCpuInventory(
            architecture="x86_64",
            model="Intel Core Ultra 9 285K",
            physical_core_count=24,
            logical_cpu_ids=tuple(range(24)),
        ),
        "memory": HostMemoryInventory(
            total_bytes=64 * 1024**3,
            available_bytes=40 * 1024**3,
            swap_total_bytes=8 * 1024**3,
            swap_free_bytes=7 * 1024**3,
        ),
        "accelerators": (
            HostAcceleratorInventory(
                device_id="gpu:0000:01:00.0",
                kind=AcceleratorKind.GPU,
                name="NVIDIA GeForce RTX 5080",
                memory_total_bytes=16_303 * 1024**2,
                driver_version="test",
            ),
        ),
        "storage": (
            HostStorageInventory(
                storage_id="storage:root",
                medium=StorageMedium.NVME,
                capacity_bytes=2_000_000_000_000,
                available_bytes=500_000_000_000,
                cache_eligible=True,
                mount_path="/",
            ),
        ),
    }
    values.update(overrides)
    return HostInventory(**values)


class HostInventorySchemaTests(unittest.TestCase):
    def test_represents_full_reference_host_tiers(self) -> None:
        inventory = _inventory()
        self.assertEqual(inventory.contract_version, HOST_INVENTORY_CONTRACT_VERSION)
        self.assertEqual(len(inventory.cpu.logical_cpu_ids), 24)
        self.assertEqual(inventory.accelerators[0].kind, AcceleratorKind.GPU)
        self.assertEqual(inventory.storage[0].medium, StorageMedium.NVME)

    def test_requires_supported_contract_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_version"):
            _inventory(contract_version="fam.hardware.inventory/v2")

    def test_requires_timezone_aware_capture(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            _inventory(captured_at=datetime(2026, 7, 16))

    def test_requires_unique_logical_cpu_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "logical CPU IDs must be unique"):
            HostCpuInventory("x86_64", (0, 0))

    def test_physical_cores_cannot_exceed_logical_cpus(self) -> None:
        with self.assertRaisesRegex(ValueError, "physical cores"):
            HostCpuInventory("x86_64", (0, 1), physical_core_count=3)

    def test_available_memory_cannot_exceed_total(self) -> None:
        with self.assertRaisesRegex(ValueError, "available memory"):
            HostMemoryInventory(100, 101)

    def test_requires_unique_accelerator_ids(self) -> None:
        accelerator = _inventory().accelerators[0]
        with self.assertRaisesRegex(ValueError, "accelerator device IDs"):
            _inventory(accelerators=(accelerator, accelerator))

    def test_requires_unique_storage_ids(self) -> None:
        storage = _inventory().storage[0]
        with self.assertRaisesRegex(ValueError, "storage IDs"):
            _inventory(storage=(storage, storage))


if __name__ == "__main__":
    unittest.main()
