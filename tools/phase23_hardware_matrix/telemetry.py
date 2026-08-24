"""Authoritative live telemetry for one installed managed-profile service."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


_SYSTEMD_PROPERTIES = (
    "ActiveState", "MainPID", "ControlGroup", "Environment",
    "MemoryCurrent", "MemoryPeak", "MemoryHigh", "MemoryMax",
    "MemorySwapCurrent", "MemorySwapMax", "CPUQuotaPerSecUSec",
    "TasksCurrent", "TasksMax",
)


def capture_profile_telemetry(
    service: Any, console_snapshot: dict[str, Any],
) -> dict[str, Any]:
    properties = _systemd_properties()
    control_group = properties.get("ControlGroup", "")
    cgroup = _cgroup_files(control_group)
    provider = _provider_models(service.ollama_url)
    policy = _console_item(console_snapshot, "resources", "policy")
    cpu = _console_item(console_snapshot, "resources", "cpu")
    memory = _console_item(console_snapshot, "resources", "memory")
    vram = _console_item(console_snapshot, "resources", "vram")
    storage = _console_item(console_snapshot, "resources", "storage")
    enabled = _console_item(console_snapshot, "experts", "enabled")
    signed = _console_item(console_snapshot, "experts", "signed")
    resident = _console_item(console_snapshot, "experts", "resident")
    return {
        "systemd": properties,
        "cgroup": cgroup,
        "provider_models": provider,
        "console": {
            "logical_cpus": cpu.get("value"),
            "policy_value": policy.get("value"),
            "policy_description": policy.get("detail"),
            "schedulable_memory": memory.get("value"),
            "schedulable_vram": vram.get("value"),
            "available_storage": storage.get("value"),
            "enabled_experts": enabled.get("value"),
            "signed_bindings": signed.get("value"),
            "resident_models": resident.get("value"),
            "resident_detail": resident.get("detail"),
        },
        "host": _host_snapshot(service.state_root),
    }


def managed_service_inactive() -> bool:
    result = subprocess.run(
        ("systemctl", "--user", "is-active", "fam-ollama.service"),
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip() == "inactive"


def _systemd_properties() -> dict[str, str]:
    command = ["systemctl", "--user", "show", "fam-ollama.service"]
    for name in _SYSTEMD_PROPERTIES:
        command.extend(("--property", name))
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=15,
    )
    return _parse_properties(completed.stdout)


def _parse_properties(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in payload.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def _cgroup_files(control_group: str) -> dict[str, str]:
    if not control_group.startswith("/") or ".." in Path(control_group).parts:
        raise RuntimeError("managed service returned an invalid cgroup path")
    root = Path("/sys/fs/cgroup") / control_group.removeprefix("/")
    values = {}
    for name in ("memory.events", "memory.pressure", "cpu.stat", "io.stat"):
        path = root / name
        values[name] = path.read_text(encoding="utf-8") if path.is_file() else ""
    return values


def _provider_models(base_url: str) -> list[dict[str, object]]:
    with urllib.request.urlopen(f"{base_url}/api/ps", timeout=10) as response:
        document = json.load(response)
    return [
        {
            "model": item.get("model") or item.get("name"),
            "size_bytes": item.get("size"),
            "size_vram_bytes": item.get("size_vram"),
            "context_length": item.get("context_length"),
        }
        for item in document.get("models", ())
    ]


def _console_item(
    snapshot: dict[str, Any], section_id: str, item_id: str,
) -> dict[str, Any]:
    for section in snapshot.get("sections", ()):
        if section.get("section_id") != section_id:
            continue
        for item in section.get("items", ()):
            if item.get("item_id") == item_id:
                return dict(item)
    raise RuntimeError(f"Console snapshot omitted {section_id}.{item_id}")


def _host_snapshot(state_root: Path) -> dict[str, object]:
    usage = shutil.disk_usage(state_root)
    return {
        "logical_cpu_count": os.cpu_count() or 1,
        "memory": _meminfo(),
        "state_filesystem": {
            "total_bytes": usage.total,
            "free_bytes": usage.free,
        },
        "nvidia": _nvidia_snapshot(),
    }


def _meminfo() -> dict[str, int]:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, separator, remainder = line.partition(":")
        if separator and key in {"MemTotal", "MemAvailable"}:
            values[key] = int(remainder.split()[0]) * 1024
    return values


def _nvidia_snapshot() -> list[dict[str, object]]:
    completed = subprocess.run(
        (
            "nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
        ),
        capture_output=True, text=True, timeout=15,
    )
    if completed.returncode != 0:
        return []
    values = []
    for index, line in enumerate(completed.stdout.splitlines()):
        fields = tuple(part.strip() for part in line.split(","))
        if len(fields) == 4:
            values.append({
                "index": index, "name": fields[0],
                "memory_total_mib": int(fields[1]),
                "memory_used_mib": int(fields[2]),
                "utilization_percent": int(fields[3]),
            })
    return values
