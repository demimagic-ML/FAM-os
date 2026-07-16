"""Read-only cgroup-v2 resource observer."""

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Protocol

from fam_os.adapters.cgroup.parsing import (
    parse_ceiling,
    parse_count_ceiling,
    parse_counter,
    parse_cpu_quota,
    parse_events,
    parse_io_counters,
    parse_io_limits,
    parse_named_counters,
    parse_pressure,
)
from fam_os.adapters.cgroup.paths import CgroupV2Paths
from fam_os.supervisor import ResourceObservationError, ResourceSnapshot


class ControlGroupLocator(Protocol):
    def control_group(self, service_id: str) -> str | None: ...


@dataclass(slots=True)
class CgroupV2ResourceObserver:
    locator: ControlGroupLocator
    paths: CgroupV2Paths = CgroupV2Paths()

    def observe(self, service_id: str) -> ResourceSnapshot | None:
        resource_group = self.locator.control_group(service_id)
        if not resource_group:
            return None
        try:
            group = self.paths.group(resource_group)
            if not group.is_dir():
                return None
            return self._read_snapshot(service_id, group)
        except (KeyError, ValueError) as error:
            raise ResourceObservationError(
                f"invalid resource data for service {service_id}"
            ) from error

    def _read_snapshot(self, service_id: str, group: Path) -> ResourceSnapshot:
        current = _read_optional(group / "memory.current")
        peak = _read_optional(group / "memory.peak")
        maximum = _read_optional(group / "memory.max")
        swap_current = _read_optional(group / "memory.swap.current")
        swap_maximum = _read_optional(group / "memory.swap.max")
        events = _read_optional(group / "memory.events")
        pressure = _read_optional(group / "memory.pressure")
        cpu = _counters(_read_optional(group / "cpu.stat"), parse_named_counters)
        io = _counters(_read_optional(group / "io.stat"), parse_io_counters)
        io_max = _read_optional(group / "io.max")
        cpu_max = _read_optional(group / "cpu.max")
        tasks_current = _read_optional(group / "pids.current")
        tasks_max = _read_optional(group / "pids.max")
        return ResourceSnapshot(
            service_id=service_id,
            memory_current_bytes=parse_counter(current) if current is not None else None,
            memory_peak_bytes=parse_counter(peak) if peak is not None else None,
            memory_limit=parse_ceiling(maximum) if maximum is not None else None,
            swap_current_bytes=parse_counter(swap_current) if swap_current is not None else None,
            swap_limit=parse_ceiling(swap_maximum) if swap_maximum is not None else None,
            cpu_usage_microseconds=cpu.get("usage_usec"),
            cpu_user_microseconds=cpu.get("user_usec"),
            cpu_system_microseconds=cpu.get("system_usec"),
            io_read_bytes=io.get("rbytes"),
            io_write_bytes=io.get("wbytes"),
            io_read_operations=io.get("rios"),
            io_write_operations=io.get("wios"),
            cpu_quota=parse_cpu_quota(cpu_max) if cpu_max is not None else None,
            tasks_current=parse_counter(tasks_current)
            if tasks_current is not None
            else None,
            tasks_limit=parse_count_ceiling(tasks_max) if tasks_max is not None else None,
            events=parse_events(events) if events is not None else (),
            pressure=parse_pressure(pressure) if pressure is not None else (),
            block_io_limits=parse_io_limits(io_max) if io_max is not None else None,
        )


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _counters(
    content: str | None, parser: Callable[[str], dict[str, int]]
) -> dict[str, int]:
    if content is None:
        return {}
    return parser(content)
