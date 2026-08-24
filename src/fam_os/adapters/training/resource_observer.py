"""Bounded Linux/NVIDIA observations for training admission."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from fam_os.expert_factory.resource_admission import (
    TrainingResourceSnapshot,
    build_resource_snapshot,
)


class LinuxTrainingResourceObserver:
    def __init__(self, storage_root: Path, now=None) -> None:
        self._storage_root = storage_root
        self._now = now or (lambda: datetime.now(UTC))

    def observe(self, snapshot_id: str) -> TrainingResourceSnapshot:
        cpu_count = os.cpu_count() or 0
        if cpu_count < 1:
            raise RuntimeError("logical CPU count is unavailable")
        memory = _available_memory()
        disk = shutil.disk_usage(self._storage_root).free
        gpu = _gpu()
        return build_resource_snapshot(
            snapshot_id=snapshot_id, logical_cpu_count=cpu_count,
            load_fraction=os.getloadavg()[0] / cpu_count,
            available_ram_bytes=memory, free_disk_bytes=disk,
            gpu_total_bytes=gpu[0], gpu_used_bytes=gpu[1],
            gpu_utilization_fraction=gpu[2], gpu_temperature_celsius=gpu[3],
            inference_conflict=_ollama_busy(), observed_at=self._now(),
        )


def _available_memory() -> int:
    for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("available memory is unavailable")


def _gpu() -> tuple[int, int, float, int]:
    result = subprocess.run((
        "nvidia-smi",
        "--query-gpu=memory.total,memory.used,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ), check=False, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError("NVIDIA training resource observation failed")
    try:
        total, used, utilization, temperature = (
            value.strip() for value in result.stdout.splitlines()[0].split(",")
        )
        return (
            int(total) * 1024**2, int(used) * 1024**2,
            float(utilization) / 100, int(temperature),
        )
    except (IndexError, ValueError) as error:
        raise RuntimeError("NVIDIA training resource response is invalid") from error


def _ollama_busy() -> bool:
    result = subprocess.run(
        ("ollama", "ps"), check=False, capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0 and len(result.stdout.splitlines()) > 1
