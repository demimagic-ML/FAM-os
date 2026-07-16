"""Provider-neutral sandbox requests, limits, and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class SandboxStatus(StrEnum):
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    UNAVAILABLE = "unavailable"


class IsolationLevel(StrEnum):
    NONE = "none"
    PROCESS_LIMITS = "process_limits"
    BUBBLEWRAP = "bubblewrap"


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    wall_seconds: float = 5.0
    memory_bytes: int = 256 * 1024**2
    cpu_seconds: int = 2
    file_bytes: int = 1024**2
    open_files: int = 32
    processes: int = 16
    output_bytes: int = 8_192

    def __post_init__(self) -> None:
        integer_limits = (
            self.memory_bytes,
            self.cpu_seconds,
            self.file_bytes,
            self.open_files,
            self.processes,
            self.output_bytes,
        )
        if not isfinite(self.wall_seconds) or self.wall_seconds <= 0:
            raise ValueError("wall_seconds must be positive and finite")
        if any(value <= 0 for value in integer_limits):
            raise ValueError("sandbox integer limits must be positive")


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    script: str
    limits: SandboxLimits = SandboxLimits()

    def __post_init__(self) -> None:
        if not self.script.strip():
            raise ValueError("sandbox script must not be empty")


@dataclass(frozen=True, slots=True)
class SandboxResult:
    status: SandboxStatus
    isolation: IsolationLevel
    wall_seconds: float
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not isfinite(self.wall_seconds) or self.wall_seconds < 0:
            raise ValueError("sandbox wall_seconds cannot be negative")
        if self.status is SandboxStatus.COMPLETED and self.exit_code is None:
            raise ValueError("completed sandbox result requires an exit code")
        if self.status is not SandboxStatus.COMPLETED and not self.reason.strip():
            raise ValueError("incomplete sandbox result requires a reason")
