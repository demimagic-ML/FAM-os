#!/usr/bin/env python3
"""Verify dedicated physical-qualification install and state are absent."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--role", choices=("requester", "expert_peer"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prefix = _safe_target(args.prefix)
    state_root = _safe_target(args.state_root)
    document = {
        "role": args.role,
        "install_absent": not prefix.exists() and not prefix.is_symlink(),
        "state_absent": not state_root.exists() and not state_root.is_symlink(),
    }
    _write_private(
        args.output, json.dumps(document, indent=2, sort_keys=True) + "\n",
    )
    return 0 if document["install_absent"] and document["state_absent"] else 1


def _safe_target(path: Path) -> Path:
    value = path.absolute()
    if value == Path("/") or len(value.parts) < 4:
        raise ValueError("refusing unsafe physical qualification removal target")
    return value


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
