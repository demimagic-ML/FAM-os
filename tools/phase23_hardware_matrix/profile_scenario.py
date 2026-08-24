"""Installed verified work and telemetry for one named hardware profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.phase19_exit.console_client import ConsoleClient
from tools.phase23_installed_matrix.local_scenario import run_local_scenario
from tools.phase23_installed_matrix.service import CandidateService

from .telemetry import capture_profile_telemetry, managed_service_inactive


MANAGED_OLLAMA_URL = "http://127.0.0.1:11435"


def run_profile_scenario(
    *, installation: Any, root: Path, source_model_root: Path, profile_id: str,
) -> dict[str, object]:
    service = CandidateService(
        installation, root / "state", root / "run",
        ollama_url=MANAGED_OLLAMA_URL,
        source_model_root=source_model_root,
        manage_ollama=True,
        validation_profile=profile_id,
    )
    telemetry: dict[str, Any]
    task: dict[str, Any]
    with service:
        task = run_local_scenario(service)
        client = ConsoleClient(
            f"http://127.0.0.1:{service.port}",
            (service.runtime_root / "console.token").read_text().strip(),
        )
        telemetry = capture_profile_telemetry(service, client.snapshot())
    cleanup = {"managed_service_inactive": managed_service_inactive()}
    profile_checks = _profile_checks(profile_id, telemetry)
    return {
        "profile_id": profile_id,
        "task": task,
        "telemetry": telemetry,
        "profile_checks": profile_checks,
        "cleanup": cleanup,
        "passed": bool(task["passed"] and profile_checks["passed"] and all(cleanup.values())),
    }


def _profile_checks(
    profile_id: str, telemetry: dict[str, Any],
) -> dict[str, object]:
    systemd = telemetry["systemd"]
    environment = systemd.get("Environment", "")
    models = telemetry["provider_models"]
    policy = telemetry["console"]["policy_description"] or ""
    events = _key_values(telemetry["cgroup"].get("memory.events", ""))
    logical_cpus = int(telemetry["host"]["logical_cpu_count"])
    console = telemetry["console"]
    provider_names = {
        item.get("model") for item in models if item.get("model")
    }
    resident_detail = str(console.get("resident_detail") or "")
    console_memory = _gib(console.get("schedulable_memory"))
    console_vram = _gib(console.get("schedulable_vram"))
    console_storage = _gib(console.get("available_storage"))
    host_memory = float(telemetry["host"]["memory"].get("MemAvailable", 0)) / 1024**3
    host_storage = float(
        telemetry["host"]["state_filesystem"].get("free_bytes", 0)
    ) / 1024**3
    physical_vram = sum(
        int(item.get("memory_total_mib") or 0)
        for item in telemetry["host"]["nvidia"]
    ) / 1024
    reserved_cpus = 1 if profile_id == "compat-cpu-16gb" else 2
    common = {
        "active_service": systemd.get("ActiveState") == "active",
        "zero_service_swap": systemd.get("MemorySwapMax") == "0",
        "zero_oom_kills": events.get("oom_kill", 0) == 0,
        "tasks_ceiling_applied": systemd.get("TasksMax") == "512",
        "profile_cpu_reserve_applied": systemd.get("CPUQuotaPerSecUSec")
        == f"{logical_cpus - reserved_cpus}s",
        "profile_visible_in_console": f"profile.{profile_id}" in policy,
        "provider_model_loaded": bool(models),
        "console_cpu_matches_host": int(console["logical_cpus"]) == logical_cpus,
        "console_memory_is_live_and_bounded": (
            0 < console_memory <= host_memory + 0.1
        ),
        "console_vram_is_live_and_bounded": (
            0 <= console_vram <= physical_vram + 0.1
        ),
        "console_storage_matches_filesystem": abs(
            console_storage - host_storage
        ) <= 0.2,
        "console_catalog_is_signed": (
            int(console["enabled_experts"]) >= 1
            and int(console["signed_bindings"]) >= 1
        ),
        "console_residency_matches_provider": (
            int(console["resident_models"]) == len(models)
            and all(name in resident_detail for name in provider_names)
        ),
    }
    if profile_id == "compat-cpu-16gb":
        specific = {
            "memory_max_16gib": systemd.get("MemoryMax") == str(16 * 1024**3),
            "memory_high_14gib": systemd.get("MemoryHigh") == str(14 * 1024**3),
            "cpu_runtime_forced": all(
                marker in environment
                for marker in (
                    "CUDA_VISIBLE_DEVICES=-1",
                    "GGML_VK_VISIBLE_DEVICES=-1",
                    "OLLAMA_LLM_LIBRARY=cpu_avx2",
                )
            ),
            "zero_provider_vram": all(
                int(item.get("size_vram_bytes") or 0) == 0 for item in models
            ),
        }
    else:
        specific = {
            "memory_ceiling_removed": systemd.get("MemoryMax") == "infinity",
            "cpu_runtime_not_forced": all(
                marker not in environment
                for marker in (
                    "CUDA_VISIBLE_DEVICES=-1",
                    "GGML_VK_VISIBLE_DEVICES=-1",
                    "OLLAMA_LLM_LIBRARY=cpu_avx2",
                )
            ),
            "provider_vram_active": any(
                int(item.get("size_vram_bytes") or 0) > 0 for item in models
            ),
            "physical_nvidia_observed": bool(telemetry["host"]["nvidia"]),
            "full_host_cpu_observed": logical_cpus >= 16,
            "full_host_ram_observed": (
                telemetry["host"]["memory"].get("MemTotal", 0) > 32 * 1024**3
            ),
            "full_host_storage_observed": (
                telemetry["host"]["state_filesystem"].get("total_bytes", 0)
                > 500 * 1024**3
            ),
        }
    checks = {**common, **specific}
    return {**checks, "passed": all(checks.values())}


def _key_values(payload: str) -> dict[str, int]:
    values = {}
    for line in payload.splitlines():
        key, separator, value = line.partition(" ")
        if separator:
            values[key] = int(value)
    return values


def _gib(value: object) -> float:
    text = str(value or "")
    number, separator, unit = text.partition(" ")
    if not separator or unit != "GiB":
        raise ValueError(f"Console capacity is not a GiB value: {text!r}")
    return float(number)
