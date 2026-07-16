"""NVIDIA GPU discovery through a bounded nvidia-smi query."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.adapters.linux.command import CommandRunner
from fam_os.scheduler.hardware import GpuProfile


NVIDIA_QUERY = (
    "nvidia-smi",
    "--query-gpu=name,memory.total,driver_version,pci.bus_id,power.limit",
    "--format=csv,noheader,nounits",
)

NVIDIA_RESOURCE_QUERY = (
    "nvidia-smi",
    "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,driver_version",
    "--format=csv,noheader,nounits",
)


@dataclass(frozen=True, slots=True)
class NvidiaResourceReading:
    index: int
    name: str
    memory_total_bytes: int
    memory_used_bytes: int
    utilization_fraction: float
    driver_version: str

    def __post_init__(self) -> None:
        if self.index < 0 or not self.name.strip() or not self.driver_version.strip():
            raise ValueError("NVIDIA resource identity is invalid")
        if not 0 <= self.memory_used_bytes <= self.memory_total_bytes:
            raise ValueError("NVIDIA memory reading is invalid")
        if not 0.0 <= self.utilization_fraction <= 1.0:
            raise ValueError("NVIDIA utilization is invalid")


def _optional_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _optional_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def parse_nvidia_smi(content: str) -> tuple[GpuProfile, ...]:
    gpus: list[GpuProfile] = []
    for line in content.splitlines():
        fields = tuple(part.strip() for part in line.split(","))
        if len(fields) != 5 or not fields[0]:
            continue
        memory_mib = _optional_int(fields[1])
        gpus.append(
            GpuProfile(
                name=fields[0],
                memory_total_bytes=memory_mib * 1024**2 if memory_mib is not None else None,
                driver_version=fields[2] or None,
                pci_bus_id=fields[3] or None,
                power_limit_watts=_optional_float(fields[4]),
            )
        )
    return tuple(gpus)


def query_nvidia_gpus(runner: CommandRunner) -> tuple[GpuProfile, ...]:
    output = runner.run(NVIDIA_QUERY)
    return parse_nvidia_smi(output) if output else ()


def parse_nvidia_resources(content: str) -> tuple[NvidiaResourceReading, ...]:
    readings: list[NvidiaResourceReading] = []
    for line in content.splitlines():
        fields = tuple(part.strip() for part in line.split(","))
        if len(fields) != 6:
            continue
        index = _optional_int(fields[0])
        total = _optional_int(fields[2])
        used = _optional_int(fields[3])
        utilization = _optional_float(fields[4])
        if None in (index, total, used, utilization) or not fields[1] or not fields[5]:
            continue
        readings.append(
            NvidiaResourceReading(
                index,
                fields[1],
                total * 1024**2,
                used * 1024**2,
                utilization / 100.0,
                fields[5],
            )
        )
    return tuple(readings)


def query_nvidia_resources(
    runner: CommandRunner,
) -> tuple[NvidiaResourceReading, ...]:
    output = runner.run(NVIDIA_RESOURCE_QUERY)
    return parse_nvidia_resources(output) if output else ()
