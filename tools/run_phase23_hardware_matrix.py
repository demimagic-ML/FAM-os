#!/usr/bin/env python3
"""Run the installed CPU-only and full-workstation release matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase23_hardware_matrix.contracts import HardwareMatrixSettings
from tools.phase23_hardware_matrix.scenario import run_hardware_matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--source-model-root", type=Path,
        default=Path("/usr/share/ollama/.ollama/models"),
    )
    parser.add_argument(
        "--owner-ollama-url", default="http://127.0.0.1:11434",
    )
    parser.add_argument(
        "--quiesce-owner-models", action="store_true",
        help="evict owner Ollama model caches before using the full GPU",
    )
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    document = run_hardware_matrix(HardwareMatrixSettings(
        repository, arguments.output_root.absolute(), arguments.run_id,
        arguments.source_model_root.absolute(),
        arguments.owner_ollama_url, arguments.quiesce_owner_models,
    ))
    print(json.dumps({
        "evidence": str(
            arguments.output_root.absolute() / "installed-hardware-matrix.json"
        ),
        "passed": document["passed"],
    }, sort_keys=True))
    return 0 if document["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
