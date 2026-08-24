"""Canonical digest of the executable verifier Python package tree."""

from __future__ import annotations

import hashlib
from pathlib import Path


def verifier_tree_digest(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("verifier artifact root must be a real directory")
    paths = tuple(
        path for path in sorted(root.rglob("*.py"))
        if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts
    )
    if not paths:
        raise ValueError("verifier artifact tree is empty")
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()
