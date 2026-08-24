"""CLI for the physical Phase 22 QLoRA smoke."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase22_training_exit.scenario import run_training_smoke
from tools.phase22_training_exit.settings import TrainingSmokePaths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--environment-directory", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--worker-script", type=Path, required=True)
    arguments = parser.parse_args()
    paths = TrainingSmokePaths(
        arguments.output_root.absolute(),
        arguments.environment_directory.absolute(),
        arguments.wheelhouse_manifest.absolute(),
        arguments.model_directory.absolute(),
        arguments.worker_script.absolute(),
    )
    evidence = run_training_smoke(paths)
    evidence_path = paths.output_root / "evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = evidence.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("training smoke evidence has no terminal result")
    passed = evidence.get("passed") is True
    print(json.dumps({
        "evidence": str(evidence_path),
        "passed": passed,
        "reason_code": result.get("reason_code"),
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
