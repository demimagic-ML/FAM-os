"""Exact requested-versus-applied resource-limit verification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fam_os.supervisor.contracts import ResourceLimits, ResourceSnapshot


class LimitVerificationStatus(StrEnum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    UNAVAILABLE = "unavailable"
    NOT_REQUESTED = "not_requested"


@dataclass(frozen=True, slots=True)
class AppliedLimitCheck:
    resource: str
    requested: int | float | None
    applied: int | float | None
    status: LimitVerificationStatus


@dataclass(frozen=True, slots=True)
class AppliedLimitsVerification:
    service_id: str
    checks: tuple[AppliedLimitCheck, ...]

    def __post_init__(self) -> None:
        if not self.service_id.strip() or not self.checks:
            raise ValueError("applied-limit verification requires identity and checks")
        resources = tuple(check.resource for check in self.checks)
        if len(set(resources)) != len(resources):
            raise ValueError("applied-limit resources must be unique")

    @property
    def passed(self) -> bool:
        statuses = {check.status for check in self.checks}
        return LimitVerificationStatus.MATCHED in statuses and statuses <= {
            LimitVerificationStatus.MATCHED,
            LimitVerificationStatus.NOT_REQUESTED,
        }


@dataclass(frozen=True, slots=True)
class _ObservedLimit:
    available: bool
    value: int | float | None


def verify_applied_limits(
    limits: ResourceLimits, snapshot: ResourceSnapshot | None, service_id: str
) -> AppliedLimitsVerification:
    if snapshot is not None and snapshot.service_id != service_id:
        raise ValueError("resource snapshot belongs to another service")
    applied = _applied(snapshot)
    requested = {
        "memory_max_bytes": limits.memory_max_bytes,
        "swap_max_bytes": limits.swap_max_bytes,
        "cpu_quota_percent": limits.cpu_quota_percent,
        "tasks_max": limits.tasks_max,
    }
    requested.update(_requested_io(limits))
    applied.update(_applied_io(snapshot, limits))
    checks = tuple(
        _check(name, value, applied[name]) for name, value in requested.items()
    )
    return AppliedLimitsVerification(service_id, checks)


def _applied(snapshot: ResourceSnapshot | None) -> dict[str, _ObservedLimit]:
    if snapshot is None:
        return {name: _ObservedLimit(False, None) for name in _RESOURCE_NAMES}
    return {
        "memory_max_bytes": _observed(snapshot.memory_limit, "maximum_bytes"),
        "swap_max_bytes": _observed(snapshot.swap_limit, "maximum_bytes"),
        "cpu_quota_percent": _observed(snapshot.cpu_quota, "maximum_percent"),
        "tasks_max": _observed(snapshot.tasks_limit, "maximum"),
    }


def _check(
    resource: str, requested: int | float | None, observed: _ObservedLimit
) -> AppliedLimitCheck:
    if requested is None:
        status = LimitVerificationStatus.NOT_REQUESTED
    elif not observed.available:
        status = LimitVerificationStatus.UNAVAILABLE
    elif observed.value is None:
        status = LimitVerificationStatus.MISMATCHED
    elif abs(float(requested) - float(observed.value)) <= 0.001:
        status = LimitVerificationStatus.MATCHED
    else:
        status = LimitVerificationStatus.MISMATCHED
    return AppliedLimitCheck(resource, requested, observed.value, status)


def _observed(value: object, attribute: str) -> _ObservedLimit:
    if value is None:
        return _ObservedLimit(False, None)
    return _ObservedLimit(True, getattr(value, attribute))


def _requested_io(limits: ResourceLimits) -> dict[str, int | None]:
    values = {}
    for item in limits.block_io_bandwidth:
        identity = f"{item.device_major}:{item.device_minor}"
        values[f"io_read_bps:{identity}"] = item.read_bytes_per_second
        values[f"io_write_bps:{identity}"] = item.write_bytes_per_second
    return values


def _applied_io(snapshot, limits) -> dict[str, _ObservedLimit]:
    result = {}
    observed = None if snapshot is None else snapshot.block_io_limits
    by_device = {} if observed is None else {
        (item.device_major, item.device_minor): item for item in observed
    }
    for item in limits.block_io_bandwidth:
        identity = f"{item.device_major}:{item.device_minor}"
        ceiling = by_device.get((item.device_major, item.device_minor))
        available = observed is not None and ceiling is not None
        result[f"io_read_bps:{identity}"] = _ObservedLimit(
            available, None if ceiling is None else ceiling.read_bytes_per_second
        )
        result[f"io_write_bps:{identity}"] = _ObservedLimit(
            available, None if ceiling is None else ceiling.write_bytes_per_second
        )
    return result


_RESOURCE_NAMES = (
    "memory_max_bytes",
    "swap_max_bytes",
    "cpu_quota_percent",
    "tasks_max",
)
