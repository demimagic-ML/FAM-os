"""Content-free Phase 23 matrix evidence and source identity."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def source_identity(repository: Path) -> dict[str, object]:
    revision = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=repository, check=True,
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    status = subprocess.run(
        ("git", "status", "--porcelain=v1", "-z"), cwd=repository, check=True,
        capture_output=True, timeout=30,
    ).stdout
    return {
        "dirty": bool(status),
        "revision": revision,
        "status_sha256": hashlib.sha256(status).hexdigest(),
    }


def host_identity() -> dict[str, object]:
    machine_id = Path("/etc/machine-id")
    value = machine_id.read_bytes().strip() if machine_id.is_file() else b"unavailable"
    return {
        "architecture": platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "machine_id_sha256": hashlib.sha256(value).hexdigest(),
        "platform": platform.platform(),
    }


def matrix_document(
    *, run_id: str, wheel: Path, wheel_sha256: str,
    source: dict[str, object], profiles: tuple[dict[str, object], ...],
) -> dict[str, object]:
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "contract_version": "fam.release.profile-matrix/v1alpha1",
        "host": host_identity(),
        "passed": bool(profiles) and all(
            bool(profile.get("passed")) for profile in profiles
        ),
        "profiles": profiles,
        "run_id": run_id,
        "source": source,
        "wheel": {"name": wheel.name, "sha256": wheel_sha256},
    }


def write_evidence(path: Path, document: dict[str, object]) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())

