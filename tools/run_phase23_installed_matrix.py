#!/usr/bin/env python3
"""Run the one-candidate installed Phase 23.3 scenario matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase23_installed_matrix.contracts import InstalledMatrixSettings
from tools.phase23_installed_matrix.scenario import run_installed_matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--source-model-root", type=Path,
        default=Path("/usr/share/ollama/.ollama/models"),
    )
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    document = run_installed_matrix(InstalledMatrixSettings(
        repository, arguments.output_root.absolute(), arguments.run_id,
        arguments.ollama_url, arguments.source_model_root.absolute(),
    ))
    print(json.dumps({
        "evidence": str(arguments.output_root.absolute() / "installed-scenario-matrix.json"),
        "passed": document["passed"],
    }, sort_keys=True))
    return 0 if document["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
