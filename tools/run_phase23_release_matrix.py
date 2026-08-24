#!/usr/bin/env python3
"""Run clean Phase 23 profiles from one newly built wheel."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from tools.phase23_release_matrix.contracts import select_profiles
from tools.phase23_release_matrix.scenario import run_matrix
from tools.phase23_release_matrix.settings import MatrixSettings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--python", type=Path, default=Path(".verification-venv/bin/python"))
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--dependency-wheelhouse", type=Path)
    parser.add_argument("--code", type=Path, default=Path("/usr/bin/code"))
    parser.add_argument("--run-id")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    run_id = args.run_id or datetime.now(UTC).strftime("phase23-%Y%m%d-%H%M%S")
    repository = args.repository.resolve()
    output = args.output_root or (
        repository / "artifacts/product/phase23/profile-matrix" / run_id
    )
    document = run_matrix(MatrixSettings(
        repository=repository,
        python=args.python.resolve(),
        output_root=output.resolve(),
        run_id=run_id,
        profiles=select_profiles(tuple(args.profile)),
        dependency_wheelhouse=(
            args.dependency_wheelhouse.resolve()
            if args.dependency_wheelhouse is not None else None
        ),
        code=args.code.resolve(),
    ))
    print(json.dumps({
        "output": str(output.resolve()),
        "passed": document["passed"],
        "profiles": {
            profile["name"]: profile["passed"] for profile in document["profiles"]
        },
    }, sort_keys=True))
    return 0 if document["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
