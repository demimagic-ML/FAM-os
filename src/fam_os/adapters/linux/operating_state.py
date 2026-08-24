"""Bounded Linux observation of user-visible operating pressure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import re

from fam_os.adaptation.resource_policy import OperatingState
from fam_os.adapters.linux.command import CommandRunner


NVIDIA_TEMPERATURE_QUERY = (
    "nvidia-smi",
    "--query-gpu=temperature.gpu",
    "--format=csv,noheader,nounits",
)
GNOME_IDLE_QUERY = (
    "gdbus",
    "call",
    "--session",
    "--dest",
    "org.gnome.Mutter.IdleMonitor",
    "--object-path",
    "/org/gnome/Mutter/IdleMonitor/Core",
    "--method",
    "org.gnome.Mutter.IdleMonitor.GetIdletime",
)
_UNSIGNED_INTEGER = re.compile(r"\b(?:uint64\s+)?([0-9]+)\b")


@dataclass(frozen=True, slots=True)
class OperatingStateObservation:
    state: OperatingState
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("operating-state reason codes must be unique")


@dataclass(slots=True)
class LinuxOperatingStateObserver:
    runner: CommandRunner
    power_supply_root: Path = Path("/sys/class/power_supply")
    thermal_root: Path = Path("/sys/class/thermal")
    hwmon_root: Path = Path("/sys/class/hwmon")
    loadavg_path: Path = Path("/proc/loadavg")
    cpu_count: Callable[[], int | None] = os.cpu_count

    def observe(self) -> OperatingStateObservation:
        reasons: list[str] = []
        battery, charging = self._battery(reasons)
        thermal = self._thermal(reasons)
        foreground = self._foreground_load(reasons)
        idle = self._idle_seconds(reasons)
        return OperatingStateObservation(
            OperatingState(battery, charging, thermal, foreground, idle),
            tuple(dict.fromkeys(reasons)),
        )

    def _battery(self, reasons: list[str]) -> tuple[float | None, bool | None]:
        try:
            supplies = tuple(sorted(self.power_supply_root.iterdir()))
        except OSError:
            return None, None
        batteries = [
            path for path in supplies
            if _read_text(path / "type").lower() == "battery"
            and _read_text(path / "scope").lower() != "device"
        ]
        if not batteries:
            return None, None
        levels: list[float] = []
        states: list[bool] = []
        for battery in batteries:
            level = _read_float(battery / "capacity")
            if level is not None and 0 <= level <= 100:
                levels.append(level)
            status = _read_text(battery / "status").lower()
            if status in {"charging", "full", "not charging"}:
                states.append(True)
            elif status == "discharging":
                states.append(False)
        if not levels:
            reasons.append("battery.reading_unavailable")
            return None, None
        charging = True if any(states) else (False if states else None)
        return min(levels), charging

    def _thermal(self, reasons: list[str]) -> float | None:
        values: list[float] = []
        paths = tuple(sorted(self.thermal_root.glob("thermal_zone*/temp")))
        paths += tuple(sorted(self.hwmon_root.glob("hwmon*/temp*_input")))
        for path in paths:
            value = _read_float(path)
            normalized = _normalize_temperature(value)
            if normalized is not None:
                values.append(normalized)
        output = self.runner.run(NVIDIA_TEMPERATURE_QUERY, 2.0)
        if output:
            for line in output.splitlines():
                normalized = _normalize_temperature(_float(line.strip()))
                if normalized is not None:
                    values.append(normalized)
        if not values:
            reasons.append("thermal.reading_unavailable")
            return None
        return max(values)

    def _foreground_load(self, reasons: list[str]) -> float:
        try:
            load = float(self.loadavg_path.read_text(encoding="utf-8").split()[0])
            processors = self.cpu_count()
            if processors is None or processors <= 0:
                raise ValueError("logical CPU count is unavailable")
        except (OSError, ValueError, IndexError):
            reasons.append("foreground.load_unavailable")
            return 1.0
        return min(1.0, max(0.0, load / processors))

    def _idle_seconds(self, reasons: list[str]) -> float:
        output = self.runner.run(GNOME_IDLE_QUERY, 2.0)
        match = None if output is None else _UNSIGNED_INTEGER.search(output)
        if match is None:
            reasons.append("idle.reading_unavailable")
            return 0.0
        return int(match.group(1)) / 1000.0


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_float(path: Path) -> float | None:
    return _float(_read_text(path))


def _float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _normalize_temperature(value: float | None) -> float | None:
    if value is None:
        return None
    normalized = value / 1000.0 if abs(value) > 1000 else value
    return normalized if -20 <= normalized <= 150 else None
