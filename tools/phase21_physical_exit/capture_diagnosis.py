#!/usr/bin/env python3
"""Capture installed diagnosis for one physical qualification host."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--role", choices=("requester", "expert_peer"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)

    from fam_os.product.bundle_installation import SignedBundleInstallation

    receipt = SignedBundleInstallation(args.prefix.resolve(), {}).diagnose()
    document = {
        "role": args.role,
        "healthy": receipt.healthy,
        "release_id": receipt.release_id,
        "issues": list(receipt.issues),
    }
    _write_private(
        args.output, json.dumps(document, indent=2, sort_keys=True) + "\n",
    )
    return 0 if receipt.healthy else 1


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


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
