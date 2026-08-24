#!/usr/bin/env python3
"""Run a real governed Phase 22 specialist checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase22_specialist_exit.recovery import (
    recover_specialist_checkpoint_evidence,
)
from tools.phase22_specialist_exit.scenario import run_specialist_checkpoint
from tools.phase22_specialist_exit.settings import SpecialistExitPaths
from tools.phase22_specialist_exit.sample_plans import (
    QUALITY256,
    SAMPLE_PLAN_IDS,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--training-environment", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--training-worker", type=Path, required=True)
    parser.add_argument("--evaluation-worker", type=Path, required=True)
    parser.add_argument(
        "--sample-plan", choices=SAMPLE_PLAN_IDS, default=QUALITY256.plan_id,
    )
    parser.add_argument("--recover-evidence", action="store_true")
    args = parser.parse_args()
    paths = SpecialistExitPaths(
        args.output_root.resolve(), args.training_environment.resolve(),
        args.training_manifest.resolve(), args.model_directory.resolve(),
        args.training_worker.resolve(), args.evaluation_worker.resolve(),
        args.recover_evidence,
    )
    evidence = (
        recover_specialist_checkpoint_evidence(
            paths, args.run_id, args.sample_plan,
        )
        if args.recover_evidence else run_specialist_checkpoint(
            paths, args.run_id, args.sample_plan,
        )
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
