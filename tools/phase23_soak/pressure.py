"""Real host-memory and GPU sampling around installed model load pressure."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.phase23_hardware_matrix.profile_scenario import run_profile_scenario
from tools.phase23_installed_matrix.escalation_scenario import run_escalation_scenario


@dataclass(slots=True)
class PressureSampler:
    interval_seconds: float = 0.2
    memory_available: list[int] = field(default_factory=list)
    gpu_memory_used_mib: list[int] = field(default_factory=list)
    gpu_utilization_percent: list[int] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def start(self) -> None:
        self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, int]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._sample()
        return {
            "samples": len(self.memory_available),
            "minimum_available_memory_bytes": min(self.memory_available),
            "maximum_gpu_memory_used_mib": max(self.gpu_memory_used_mib),
            "maximum_gpu_utilization_percent": max(
                self.gpu_utilization_percent
            ),
        }

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def _sample(self) -> None:
        self.memory_available.append(_available_memory())
        gpu_memory, utilization = _nvidia()
        self.gpu_memory_used_mib.append(gpu_memory)
        self.gpu_utilization_percent.append(utilization)


def run_model_pressure(
    *, installation: Any, repository: Path, root: Path,
    ollama_url: str, source_model_root: Path, full: bool,
) -> dict[str, object]:
    sampler = PressureSampler()
    sampler.start()
    try:
        if full:
            scenario = run_escalation_scenario(
                installation=installation,
                repository=repository,
                root=root,
                ollama_url=ollama_url,
                source_model_root=source_model_root,
                manage_ollama=True,
                validation_profile="full-reference-workstation",
            )
            models = tuple(scenario.get("strong_probe_models", ()))
            chain_models = tuple(scenario.get("chain_models", ()))
            scenario_passed = scenario.get("passed") is True
        else:
            light = run_profile_scenario(
                installation=installation,
                root=root,
                source_model_root=source_model_root,
                profile_id="full-reference-workstation",
            )
            models = tuple(
                str(item.get("model"))
                for item in light["telemetry"]["provider_models"]
            )
            chain_models = models
            scenario_passed = light.get("passed") is True
    finally:
        telemetry = sampler.stop()
    expected = (
        {"laguna-xs.2:q4_K_M", "gemma4:26b"}
        if full else {"qwen3:1.7b"}
    )
    return {
        "full_pressure": full,
        "models": models,
        "chain_models": chain_models,
        "telemetry": telemetry,
        "passed": bool(
            scenario_passed
            and expected <= set((*models, *chain_models))
            and telemetry["samples"] >= 2
            and (
                telemetry["maximum_gpu_memory_used_mib"] > 0
                if full else True
            )
        ),
    }


def _available_memory() -> int:
    for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable is unavailable")


def _nvidia() -> tuple[int, int]:
    completed = subprocess.run(
        (
            "nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ),
        capture_output=True, text=True, timeout=10,
    )
    values = []
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            fields = tuple(part.strip() for part in line.split(","))
            if len(fields) == 2:
                values.append((int(fields[0]), int(fields[1])))
    return (
        max((item[0] for item in values), default=0),
        max((item[1] for item in values), default=0),
    )
