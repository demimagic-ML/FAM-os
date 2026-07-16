"""Provider-neutral hardware profile contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _require_non_negative(name: str, values: tuple[int | float | None, ...]) -> None:
    if any(value is not None and value < 0 for value in values):
        raise ValueError(f"{name} values cannot be negative")


@dataclass(frozen=True, slots=True)
class OperatingSystemProfile:
    system: str
    release: str
    machine: str

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.system, self.release, self.machine)):
            raise ValueError("operating-system fields must not be empty")


@dataclass(frozen=True, slots=True)
class CpuProfile:
    model: str | None
    logical_cpus: int | None

    def __post_init__(self) -> None:
        if self.logical_cpus is not None and self.logical_cpus <= 0:
            raise ValueError("logical_cpus must be positive when known")


@dataclass(frozen=True, slots=True)
class MemoryProfile:
    total_bytes: int | None
    available_bytes: int | None
    swap_total_bytes: int | None
    swap_free_bytes: int | None

    def __post_init__(self) -> None:
        _require_non_negative(
            "memory",
            (self.total_bytes, self.available_bytes, self.swap_total_bytes, self.swap_free_bytes),
        )


@dataclass(frozen=True, slots=True)
class StorageProfile:
    root_total_bytes: int
    root_used_bytes: int
    root_free_bytes: int

    def __post_init__(self) -> None:
        _require_non_negative(
            "storage",
            (self.root_total_bytes, self.root_used_bytes, self.root_free_bytes),
        )


@dataclass(frozen=True, slots=True)
class GpuProfile:
    name: str
    memory_total_bytes: int | None
    driver_version: str | None
    pci_bus_id: str | None
    power_limit_watts: float | None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("GPU name must not be empty")
        _require_non_negative("GPU", (self.memory_total_bytes, self.power_limit_watts))


@dataclass(frozen=True, slots=True)
class RuntimeVersion:
    runtime_id: str
    version: str | None

    def __post_init__(self) -> None:
        if not self.runtime_id.strip():
            raise ValueError("runtime_id must not be empty")


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    schema_version: int
    captured_at: datetime
    hostname: str
    operating_system: OperatingSystemProfile
    cpu: CpuProfile
    memory: MemoryProfile
    storage: StorageProfile
    gpus: tuple[GpuProfile, ...] = ()
    npu_device_paths: tuple[str, ...] = ()
    runtimes: tuple[RuntimeVersion, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported hardware profile schema_version")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        if not self.hostname.strip():
            raise ValueError("hostname must not be empty")
        if any(not path.strip() for path in self.npu_device_paths):
            raise ValueError("NPU device paths must not be empty")

    def runtime_version(self, runtime_id: str) -> str | None:
        for runtime in self.runtimes:
            if runtime.runtime_id == runtime_id:
                return runtime.version
        return None

