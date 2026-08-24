"""Seal the deterministic evaluator-owned suite before training begins."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from tools.phase22_specialist_exit.fixtures import evaluation_suite_bytes


@dataclass(frozen=True, slots=True)
class SealedEvaluationSuite:
    path: Path
    sha256: str
    case_count: int


def seal_evaluation_suite(root: Path) -> SealedEvaluationSuite:
    root.mkdir(mode=0o700)
    payload = evaluation_suite_bytes()
    path = root / "evaluation-suite.jsonl"
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return SealedEvaluationSuite(
        path, hashlib.sha256(payload).hexdigest(), payload.count(b"\n"),
    )


def load_sealed_evaluation_suite(root: Path) -> SealedEvaluationSuite:
    """Load only the exact owner-private suite compiled by this checkpoint."""
    path = root / "evaluation-suite.jsonl"
    details = path.stat(follow_symlinks=False)
    if path.is_symlink() or not path.is_file() or details.st_uid != os.geteuid():
        raise PermissionError("sealed evaluation suite ownership is invalid")
    if stat.S_IMODE(details.st_mode) != 0o600:
        raise PermissionError("sealed evaluation suite mode is invalid")
    payload = path.read_bytes()
    if payload != evaluation_suite_bytes():
        raise PermissionError("sealed evaluation suite content changed")
    return SealedEvaluationSuite(
        path, hashlib.sha256(payload).hexdigest(), payload.count(b"\n"),
    )
