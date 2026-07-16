"""Provider-neutral service lifecycle and resource-observation language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


_SERVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@:-]{0,127}$")
_ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_COMMAND_ARGUMENTS = 256
_MAX_ARGUMENT_LENGTH = 4096
_MAX_ENVIRONMENT_ENTRIES = 128
_MAX_ENVIRONMENT_VALUE_LENGTH = 8192


class ServiceState(StrEnum):
    UNKNOWN = "unknown"
    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAILED = "failed"


class PressureScope(StrEnum):
    SOME = "some"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    memory_max_bytes: int | None = None
    swap_max_bytes: int | None = None
    cpu_quota_percent: float | None = None
    tasks_max: int | None = None
    block_io_bandwidth: tuple["BlockIoBandwidthLimit", ...] = ()

    def __post_init__(self) -> None:
        byte_limits = (self.memory_max_bytes, self.swap_max_bytes)
        if any(value is not None and value < 0 for value in byte_limits):
            raise ValueError("memory and swap limits cannot be negative")
        if self.cpu_quota_percent is not None and (
            not isfinite(self.cpu_quota_percent) or self.cpu_quota_percent <= 0
        ):
            raise ValueError("cpu_quota_percent must be positive")
        if self.tasks_max is not None and self.tasks_max <= 0:
            raise ValueError("tasks_max must be positive")
        devices = tuple((item.device_major, item.device_minor) for item in self.block_io_bandwidth)
        if len(set(devices)) != len(devices):
            raise ValueError("block I/O limit devices must be unique")


@dataclass(frozen=True, slots=True)
class BlockIoBandwidthLimit:
    device_path: str
    device_major: int
    device_minor: int
    read_bytes_per_second: int | None
    write_bytes_per_second: int | None

    def __post_init__(self) -> None:
        if not self.device_path.startswith("/dev/") or _has_control(self.device_path):
            raise ValueError("block I/O device path must be an absolute device")
        if self.device_major < 0 or self.device_minor < 0:
            raise ValueError("block I/O device numbers cannot be negative")
        rates = (self.read_bytes_per_second, self.write_bytes_per_second)
        if all(value is None for value in rates):
            raise ValueError("block I/O limit requires a read or write rate")
        if any(value is not None and value <= 0 for value in rates):
            raise ValueError("block I/O bandwidth rates must be positive")


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    service_id: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()
    limits: ResourceLimits = ResourceLimits()

    def __post_init__(self) -> None:
        _validate_service_id(self.service_id)
        invalid_argument = any(
            not item or len(item) > _MAX_ARGUMENT_LENGTH or _has_control(item)
            for item in self.command
        )
        if not self.command or len(self.command) > _MAX_COMMAND_ARGUMENTS or invalid_argument:
            raise ValueError("command must contain non-empty arguments")
        if len(self.environment) > _MAX_ENVIRONMENT_ENTRIES:
            raise ValueError("environment has too many entries")
        keys = [key for key, _ in self.environment]
        if len(keys) != len(set(keys)):
            raise ValueError("environment keys must be unique")
        for key, value in self.environment:
            if (
                not _ENVIRONMENT_KEY.fullmatch(key)
                or len(value) > _MAX_ENVIRONMENT_VALUE_LENGTH
                or _has_control(value)
            ):
                raise ValueError("environment entry is invalid")


@dataclass(frozen=True, slots=True)
class ServiceStatus:
    service_id: str
    state: ServiceState
    substate: str | None = None
    result: str | None = None
    main_pid: int | None = None
    resource_group: str | None = None

    def __post_init__(self) -> None:
        _validate_service_id(self.service_id)
        if self.main_pid is not None and self.main_pid < 0:
            raise ValueError("main_pid cannot be negative")


@dataclass(frozen=True, slots=True)
class ResourceEvent:
    name: str
    count: int

    def __post_init__(self) -> None:
        if not self.name or self.count < 0:
            raise ValueError("resource event requires a name and non-negative count")


@dataclass(frozen=True, slots=True)
class PressureSample:
    scope: PressureScope
    average_10: float
    average_60: float
    average_300: float
    total_stall_microseconds: int

    def __post_init__(self) -> None:
        averages = (self.average_10, self.average_60, self.average_300)
        if (
            any(not isfinite(value) or value < 0 for value in averages)
            or self.total_stall_microseconds < 0
        ):
            raise ValueError("pressure measurements cannot be negative")


@dataclass(frozen=True, slots=True)
class ResourceCeiling:
    maximum_bytes: int | None

    def __post_init__(self) -> None:
        if self.maximum_bytes is not None and self.maximum_bytes < 0:
            raise ValueError("resource ceiling cannot be negative")

    @property
    def unbounded(self) -> bool:
        return self.maximum_bytes is None


@dataclass(frozen=True, slots=True)
class CpuQuotaCeiling:
    maximum_percent: float | None

    def __post_init__(self) -> None:
        if self.maximum_percent is not None and (
            not isfinite(self.maximum_percent) or self.maximum_percent <= 0
        ):
            raise ValueError("CPU quota ceiling must be positive when bounded")

    @property
    def unbounded(self) -> bool:
        return self.maximum_percent is None


@dataclass(frozen=True, slots=True)
class CountCeiling:
    maximum: int | None

    def __post_init__(self) -> None:
        if self.maximum is not None and self.maximum < 0:
            raise ValueError("count ceiling cannot be negative")

    @property
    def unbounded(self) -> bool:
        return self.maximum is None


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    service_id: str
    memory_current_bytes: int | None = None
    memory_peak_bytes: int | None = None
    memory_limit: ResourceCeiling | None = None
    swap_current_bytes: int | None = None
    swap_limit: ResourceCeiling | None = None
    cpu_usage_microseconds: int | None = None
    cpu_user_microseconds: int | None = None
    cpu_system_microseconds: int | None = None
    io_read_bytes: int | None = None
    io_write_bytes: int | None = None
    io_read_operations: int | None = None
    io_write_operations: int | None = None
    cpu_quota: CpuQuotaCeiling | None = None
    tasks_current: int | None = None
    tasks_limit: CountCeiling | None = None
    events: tuple[ResourceEvent, ...] = ()
    pressure: tuple[PressureSample, ...] = ()
    block_io_limits: tuple["BlockIoBandwidthCeiling", ...] | None = None

    def __post_init__(self) -> None:
        _validate_service_id(self.service_id)
        values = (
            self.memory_current_bytes,
            self.memory_peak_bytes,
            self.swap_current_bytes,
            self.cpu_usage_microseconds,
            self.cpu_user_microseconds,
            self.cpu_system_microseconds,
            self.io_read_bytes,
            self.io_write_bytes,
            self.io_read_operations,
            self.io_write_operations,
            self.tasks_current,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("resource measurements cannot be negative")

    def event_count(self, name: str) -> int | None:
        return next((event.count for event in self.events if event.name == name), None)


@dataclass(frozen=True, slots=True)
class BlockIoBandwidthCeiling:
    device_major: int
    device_minor: int
    read_bytes_per_second: int | None
    write_bytes_per_second: int | None

    def __post_init__(self) -> None:
        if self.device_major < 0 or self.device_minor < 0:
            raise ValueError("block I/O ceiling device numbers cannot be negative")
        rates = (self.read_bytes_per_second, self.write_bytes_per_second)
        if any(value is not None and value <= 0 for value in rates):
            raise ValueError("block I/O ceiling rates must be positive")


def _validate_service_id(service_id: str) -> None:
    if not _SERVICE_ID.fullmatch(service_id):
        raise ValueError("service_id contains unsupported characters")


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
