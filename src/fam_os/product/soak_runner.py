"""Real thermal, memory, storage, and crash-recovery soak runner."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from fam_os.product.soak_contracts import SoakReport


@dataclass(slots=True)
class SoakAccumulator:
    rss: list[int] = field(default_factory=list)
    free_storage: list[int] = field(default_factory=list)
    temperatures: list[float] = field(default_factory=list)
    storage_cycles: int = 0
    storage_bytes: int = 0
    crashes: int = 0
    recoveries: int = 0
    failures: list[str] = field(default_factory=list)


def run_soak(root: Path, duration_seconds: float, interval_seconds: float) -> SoakReport:
    if duration_seconds <= 0 or interval_seconds <= 0:
        raise ValueError("soak duration and interval must be positive")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = SoakAccumulator()
    started = time.monotonic()
    cycle = 0
    while time.monotonic() - started < duration_seconds:
        _sample(root, state)
        _storage_cycle(root, state, cycle)
        if cycle % 20 == 0:
            _crash_recovery_cycle(state)
        cycle += 1
        time.sleep(min(interval_seconds, max(0, duration_seconds - (time.monotonic() - started))))
    elapsed = time.monotonic() - started
    _evaluate(state)
    return _report(state, elapsed)


def _sample(root: Path, state: SoakAccumulator) -> None:
    state.rss.append(_rss_bytes())
    state.free_storage.append(shutil.disk_usage(root).free)
    state.temperatures.extend(_temperatures())


def _storage_cycle(root: Path, state: SoakAccumulator, cycle: int) -> None:
    path = root / "storage-probe.bin"
    payload = bytes((cycle + index) % 251 for index in range(4096))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != payload:
        state.failures.append("storage_readback_mismatch")
    path.unlink(missing_ok=True)
    state.storage_cycles += 1
    state.storage_bytes += len(payload)


def _crash_recovery_cycle(state: SoakAccumulator) -> None:
    crashed = subprocess.run(
        (sys.executable, "-c", "raise SystemExit(17)"), check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    state.crashes += int(crashed.returncode == 17)
    recovered = subprocess.run(
        (sys.executable, "-c", "raise SystemExit(0)"), check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    state.recoveries += int(recovered.returncode == 0)


def _rss_bytes() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("VmRSS is unavailable")


def _temperatures() -> list[float]:
    values = []
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            value = float(path.read_text().strip()) / 1000
        except (OSError, ValueError):
            continue
        if -20 <= value <= 150:
            values.append(value)
    return values


def _evaluate(state: SoakAccumulator) -> None:
    if state.recoveries != state.crashes:
        state.failures.append("crash_recovery_mismatch")
    if state.rss[-1] - state.rss[0] > 16 * 1024 * 1024:
        state.failures.append("rss_growth_exceeded_16_mib")
    if state.temperatures and max(state.temperatures) >= 95:
        state.failures.append("thermal_limit_reached")
    if min(state.free_storage) < 1024 * 1024 * 1024:
        state.failures.append("storage_headroom_below_1_gib")


def _report(state: SoakAccumulator, duration: float) -> SoakReport:
    return SoakReport(
        "full-reference-workstation", duration, len(state.rss), state.rss[0],
        max(state.rss), state.rss[-1], min(state.free_storage),
        state.storage_cycles, state.storage_bytes, len(state.temperatures),
        max(state.temperatures) if state.temperatures else None,
        state.crashes, state.recoveries, tuple(state.failures), not state.failures,
    )
