"""Privacy-reviewed mapping from read-only Linux probes to Phase 2 resources."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.adapters.linux.command import CommandRunner
from fam_os.adapters.linux.discovery import LinuxHardwareDiscovery
from fam_os.adapters.linux.nvidia import NvidiaResourceReading, query_nvidia_resources
from fam_os.scheduler.configuration import (
    AcceleratorRuntimeState,
    DiscoveredResourceState,
    StorageRuntimeState,
)
from fam_os.scheduler.hardware import HardwareProfile
from fam_os.scheduler.resources import (
    AcceleratorKind,
    HostAcceleratorInventory,
    HostCpuInventory,
    HostInventory,
    HostMemoryInventory,
    HostStorageInventory,
    StorageMedium,
)


@dataclass(slots=True)
class PrivacyReviewedLinuxResourceDiscovery:
    hardware: LinuxHardwareDiscovery
    runner: CommandRunner
    inventory_id: str
    state_id: str
    storage_medium: StorageMedium = StorageMedium.NVME

    def collect(self) -> DiscoveredResourceState:
        profile = self.hardware.collect()
        readings = query_nvidia_resources(self.runner)
        return build_privacy_reviewed_resource_state(
            profile, readings, self.inventory_id, self.state_id, self.storage_medium
        )


def build_privacy_reviewed_resource_state(
    profile: HardwareProfile,
    readings: tuple[NvidiaResourceReading, ...],
    inventory_id: str,
    state_id: str,
    storage_medium: StorageMedium = StorageMedium.NVME,
) -> DiscoveredResourceState:
    memory = _memory(profile)
    inventory = HostInventory(
        inventory_id,
        profile.captured_at,
        profile.operating_system.system,
        profile.operating_system.release,
        _cpu(profile),
        memory,
        (_storage(profile, storage_medium),),
        _accelerators(profile),
    )
    current_by_index = {reading.index: reading.memory_used_bytes for reading in readings}
    accelerators = tuple(
        AcceleratorRuntimeState(item.device_id, current_by_index.get(index, 0))
        for index, item in enumerate(inventory.accelerators)
        if item.kind is AcceleratorKind.GPU
    )
    return DiscoveredResourceState(
        state_id,
        profile.captured_at,
        inventory,
        memory.total_bytes - memory.available_bytes,
        memory.swap_total_bytes,
        memory.swap_total_bytes - memory.swap_free_bytes,
        accelerators=accelerators,
        storage=(StorageRuntimeState("storage-root", 0),),
    )


def _cpu(profile: HardwareProfile) -> HostCpuInventory:
    logical = profile.cpu.logical_cpus
    if logical is None:
        raise ValueError("live resource discovery requires a logical CPU count")
    return HostCpuInventory(
        profile.operating_system.machine,
        tuple(range(logical)),
        profile.cpu.model,
    )


def _memory(profile: HardwareProfile) -> HostMemoryInventory:
    total = profile.memory.total_bytes
    available = profile.memory.available_bytes
    swap_total = profile.memory.swap_total_bytes
    swap_free = profile.memory.swap_free_bytes
    if total is None or available is None or swap_total is None or swap_free is None:
        raise ValueError("live resource discovery requires complete memory counters")
    return HostMemoryInventory(total, available, swap_total, swap_free)


def _storage(
    profile: HardwareProfile, medium: StorageMedium
) -> HostStorageInventory:
    return HostStorageInventory(
        "storage-root",
        medium,
        profile.storage.root_total_bytes,
        profile.storage.root_free_bytes,
        True,
        None,
    )


def _accelerators(
    profile: HardwareProfile,
) -> tuple[HostAcceleratorInventory, ...]:
    gpus = tuple(
        HostAcceleratorInventory(
            f"gpu-{index}",
            AcceleratorKind.GPU,
            gpu.name,
            gpu.memory_total_bytes,
            gpu.driver_version,
        )
        for index, gpu in enumerate(profile.gpus)
    )
    npus = tuple(
        HostAcceleratorInventory(
            f"npu-{index}", AcceleratorKind.NPU, "Linux accelerator device"
        )
        for index, _ in enumerate(profile.npu_device_paths)
    )
    return (*gpus, *npus)
