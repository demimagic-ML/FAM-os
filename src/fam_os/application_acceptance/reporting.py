"""Canonical JSON report and privacy-reviewed host summary."""

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path


def host_profile(root: Path):
    memory = _meminfo()
    disk = os.statvfs(root)
    return {
        "logical_cpus": os.cpu_count(),
        "memory_total_bytes": memory.get("MemTotal", 0) * 1024,
        "memory_available_bytes": memory.get("MemAvailable", 0) * 1024,
        "workspace_disk_total_bytes": disk.f_blocks * disk.f_frsize,
        "workspace_disk_available_bytes": disk.f_bavail * disk.f_frsize,
        "gpu": _gpu(),
        "measurement_scope": (
            "operation latency/context plus FAM process CPU/RSS/I/O; host inventory "
            "and global GPU memory are separately reported"
        ),
    }


def write_report(path: Path, report, transcripts):
    path.parent.mkdir(parents=True, exist_ok=True)
    document = asdict(report)
    document["shell_transcripts"] = transcripts
    encoded = json.dumps(document, sort_keys=True, indent=2) + "\n"
    path.write_text(encoded, encoding="utf-8")


def _meminfo():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, raw = line.split(":", 1)
        values[key] = int(raw.strip().split()[0])
    return values


def _gpu():
    command = (
        "/usr/bin/nvidia-smi", "--query-gpu=name,memory.total,memory.used",
        "--format=csv,noheader,nounits",
    )
    try:
        output = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=5,
            env={},
        ).stdout.strip()
        name, total, used = (item.strip() for item in output.split(",", 2))
        return {
            "name": name, "memory_total_mib": int(total),
            "memory_used_mib": int(used),
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"available": False}
