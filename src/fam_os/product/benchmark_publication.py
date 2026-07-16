"""Reproducible, profile-separated benchmark publication assembly."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


BENCHMARK_PUBLICATION_VERSION = "fam.product.benchmarks/v1alpha1"


@dataclass(frozen=True, slots=True)
class ProfileBenchmarkSummary:
    profile_id: str
    source_path: str
    source_sha256: str
    status: str
    measurements: tuple[tuple[str, str], ...]
    reproduction_command: str


@dataclass(frozen=True, slots=True)
class BenchmarkPublication:
    minimum_hardware: ProfileBenchmarkSummary
    full_workstation: ProfileBenchmarkSummary
    profiles_kept_separate: bool
    passed: bool
    contract_version: str = BENCHMARK_PUBLICATION_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_publication(cpu_path: Path, workstation_path: Path) -> BenchmarkPublication:
    cpu = json.loads(cpu_path.read_text())["payload"]
    workstation = json.loads(workstation_path.read_text())
    if cpu["validation_profile_id"] != "compat-cpu-16gb":
        raise ValueError("minimum benchmark uses the wrong profile")
    if workstation["constraints"]["profile_id"] != "full-reference-workstation":
        raise ValueError("workstation benchmark uses the wrong profile")
    minimum = ProfileBenchmarkSummary(
        "compat-cpu-16gb", str(cpu_path), _digest(cpu_path), "passed",
        (("service_memory_peak_bytes", str(cpu["service_memory_peak_bytes"])),
         ("service_swap_peak_bytes", str(cpu["service_swap_peak_bytes"])),
         ("inference_attempts", str(len(cpu["attempts"]))),
         ("executed_attempts", str(sum(item["inference_executed"] for item in cpu["attempts"]))),),
        "python tools/run_cpu_only_baseline.py --profile configs/profiles/compat-cpu-16gb.json",
    )
    full = ProfileBenchmarkSummary(
        "full-reference-workstation", str(workstation_path), _digest(workstation_path),
        workstation["status"],
        (("verified", str(workstation["result"]["verified"]).lower()),
         ("memory_peak_bytes", str(workstation["resources"]["memory_peak_bytes"])),
         ("gpu_allowed", str(workstation["constraints"]["gpu_allowed"]).lower()),
         ("successful_model", workstation["attempts"][-1]["model_ref"]),
         ("successful_wall_seconds", str(workstation["attempts"][-1]["metrics"]["wall_seconds"]))),
        "python tools/run_verified_parity.py --config configs/benchmarks/economical-to-gemma-escalation.json",
    )
    passed = cpu["service_swap_peak_bytes"] == 0 and workstation["result"]["verified"]
    return BenchmarkPublication(minimum, full, True, passed)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
