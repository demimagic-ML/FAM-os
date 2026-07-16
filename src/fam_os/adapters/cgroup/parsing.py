"""Pure parsers for cgroup-v2 memory controller files."""

from fam_os.supervisor import (
    BlockIoBandwidthCeiling,
    CountCeiling,
    CpuQuotaCeiling,
    PressureSample,
    PressureScope,
    ResourceCeiling,
    ResourceEvent,
)


def parse_counter(value: str) -> int:
    parsed = int(value.strip())
    if parsed < 0:
        raise ValueError("cgroup counter cannot be negative")
    return parsed


def parse_ceiling(value: str) -> ResourceCeiling:
    stripped = value.strip()
    return ResourceCeiling(None if stripped == "max" else parse_counter(stripped))


def parse_count_ceiling(value: str) -> CountCeiling:
    stripped = value.strip()
    return CountCeiling(None if stripped == "max" else parse_counter(stripped))


def parse_cpu_quota(value: str) -> CpuQuotaCeiling:
    quota, period = value.split()
    period_value = parse_counter(period)
    if period_value == 0:
        raise ValueError("CPU quota period must be positive")
    if quota == "max":
        return CpuQuotaCeiling(None)
    return CpuQuotaCeiling(parse_counter(quota) / period_value * 100.0)


def parse_events(output: str) -> tuple[ResourceEvent, ...]:
    events = []
    for line in output.splitlines():
        if not line.strip():
            continue
        name, value = line.split()
        events.append(ResourceEvent(name, parse_counter(value)))
    return tuple(events)


def parse_named_counters(output: str) -> dict[str, int]:
    counters: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 2:
            counters[fields[0]] = parse_counter(fields[1])
    return counters


def parse_io_counters(output: str) -> dict[str, int]:
    counters = {name: 0 for name in ("rbytes", "wbytes", "rios", "wios")}
    for line in output.splitlines():
        for field in line.split()[1:]:
            name, value = field.split("=", 1)
            if name in counters:
                counters[name] += parse_counter(value)
    return counters


def parse_io_limits(output: str) -> tuple[BlockIoBandwidthCeiling, ...]:
    limits = []
    for line in output.splitlines():
        if not line.strip():
            continue
        device, *fields = line.split()
        major, minor = (int(value) for value in device.split(":", 1))
        values = dict(field.split("=", 1) for field in fields)
        limits.append(BlockIoBandwidthCeiling(
            major, minor, _rate(values.get("rbps")), _rate(values.get("wbps"))
        ))
    return tuple(limits)


def _rate(value: str | None) -> int | None:
    return None if value in (None, "max") else parse_counter(value)


def parse_pressure(output: str) -> tuple[PressureSample, ...]:
    return tuple(_parse_pressure_line(line) for line in output.splitlines() if line.strip())


def _parse_pressure_line(line: str) -> PressureSample:
    scope_value, *fields = line.split()
    values = dict(field.split("=", 1) for field in fields)
    return PressureSample(
        scope=PressureScope(scope_value),
        average_10=float(values["avg10"]),
        average_60=float(values["avg60"]),
        average_300=float(values["avg300"]),
        total_stall_microseconds=parse_counter(values["total"]),
    )
