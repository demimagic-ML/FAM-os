"""Durable replay and restart state for SQLite engineering attempts."""

from __future__ import annotations

import os
from pathlib import Path

from fam_os.adapters.database.sqlite_storage import private_directories
from fam_os.adapters.filesystem.candidate_io import atomic_write, read_regular


def claim_attempt(root: Path, plan_id: str) -> None:
    target = attempt_path(root, plan_id)
    private_directories(root, target.parent)
    descriptor = os.open(
        target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(b"started\n")
        stream.flush()
        os.fsync(stream.fileno())


def record_backup(
    root: Path, plan_id: str, backup_id: str, sha256: str, size: int, relative: str,
) -> None:
    write_state(root, plan_id, f"backup:{backup_id}:{sha256}:{size}:{relative}\n")


def complete_attempt(root: Path, plan_id: str, receipt_id: str) -> None:
    write_state(root, plan_id, f"verified:{receipt_id}\n")


def recover_attempt(root: Path, plan_id: str, receipt_id: str) -> None:
    write_state(root, plan_id, f"recovered:{receipt_id}\n")


def read_attempt(root: Path, plan_id: str) -> str:
    return read_regular(attempt_path(root, plan_id), 4096).decode("ascii", "strict").strip()


def backup_state(value: str) -> tuple[str, str, int, str] | None:
    parts = value.split(":", 4)
    if len(parts) == 5 and parts[0] == "backup" and all(parts[1:]):
        try:
            size = int(parts[3])
        except ValueError:
            return None
        if len(parts[2]) == 64 and size > 0:
            return parts[1], parts[2], size, parts[4]
    return None


def attempt_path(root: Path, plan_id: str) -> Path:
    if not plan_id or "/" in plan_id or "\\" in plan_id or plan_id in {".", ".."}:
        raise ValueError("database plan identity is not filesystem-safe")
    return root / ".fam" / "database" / "attempts" / f"{plan_id}.state"


def write_state(root: Path, plan_id: str, value: str) -> None:
    target = attempt_path(root, plan_id)
    if not target.exists():
        raise FileNotFoundError("database attempt state is unavailable")
    atomic_write(target, value.encode("ascii"), 0o600)
