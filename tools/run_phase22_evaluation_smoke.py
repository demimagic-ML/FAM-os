from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

from tools.phase22_evaluation_exit.scenario import run_evaluation_smoke
from tools.phase22_evaluation_exit.settings import EvaluationSmokePaths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-artifact", type=Path, required=True)
    parser.add_argument("--environment-directory", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--worker-script", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument(
        "--run-id", default="phase22-physical-evaluation",
        help="Unique one-use evaluation identity",
    )
    arguments = parser.parse_args()
    paths = EvaluationSmokePaths(
        arguments.training_artifact.absolute(),
        arguments.environment_directory.absolute(),
        arguments.wheelhouse_manifest.absolute(),
        arguments.model_directory.absolute(), arguments.worker_script.absolute(),
        arguments.suite.absolute(),
    )
    evidence = run_evaluation_smoke(paths, arguments.run_id)
    suffix = "" if arguments.run_id == "phase22-physical-evaluation" else (
        f"-{arguments.run_id}"
    )
    evidence_path = paths.training_artifact / f"evaluation-evidence{suffix}.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    decision = evidence.get("decision")
    promotable = decision.get("promotable") if isinstance(decision, Mapping) else None
    print(json.dumps({
        "evidence": str(evidence_path), "passed": evidence.get("passed"),
        "promotable": promotable,
    }, sort_keys=True))
    return 0 if evidence.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
