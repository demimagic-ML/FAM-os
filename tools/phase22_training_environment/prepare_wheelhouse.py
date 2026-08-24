"""Resolve the exact training dependency closure into a hashed wheelhouse."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.phase22_training_environment.wheel_manifest import build_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args(argv)
    arguments.wheelhouse.mkdir(parents=True, exist_ok=True)
    subprocess.run((
        sys.executable, "-m", "pip", "download", "--only-binary=:all:",
        "--dest", str(arguments.wheelhouse), "--requirement",
        str(arguments.requirements),
    ), check=True)
    document = build_manifest(arguments.requirements, arguments.wheelhouse)
    arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = arguments.manifest.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    temporary.replace(arguments.manifest)
    print(json.dumps({
        "manifest": str(arguments.manifest),
        "manifest_sha256": document["manifest_sha256"],
        "wheel_count": len(document["wheels"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
