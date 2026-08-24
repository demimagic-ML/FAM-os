"""Verify a wheelhouse and install it without network access."""

from __future__ import annotations

import argparse
import json
import subprocess
import venv
from pathlib import Path

from tools.phase22_training_environment.wheel_manifest import verify_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    arguments = parser.parse_args(argv)
    requirements = arguments.requirements.absolute()
    wheelhouse = arguments.wheelhouse.absolute()
    manifest = arguments.manifest.absolute()
    environment = arguments.environment.absolute()
    document = json.loads(manifest.read_text("utf-8"))
    verify_manifest(document, requirements, wheelhouse)
    if environment.exists():
        raise FileExistsError("training environment already exists; use a new digest path")
    venv.EnvBuilder(with_pip=True, clear=False, symlinks=True).create(
        environment,
    )
    python = environment / "bin/python"
    subprocess.run((
        str(python), "-m", "pip", "install", "--no-index",
        "--find-links", str(wheelhouse), "--requirement",
        str(requirements),
    ), check=True, cwd=environment.parent)
    # Do not let repository-local ``src/*.egg-info`` participate in pip's
    # environment scan merely because this tool was launched from the checkout.
    subprocess.run(
        (str(python), "-m", "pip", "check"), check=True,
        cwd=environment.parent,
    )
    marker = environment / "fam-wheelhouse-manifest.json"
    marker.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "environment": str(environment),
        "manifest_sha256": document["manifest_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
