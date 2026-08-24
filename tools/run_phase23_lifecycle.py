#!/usr/bin/env python3
"""CLI for the signed installed Phase 23.8 lifecycle gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase23_lifecycle.contracts import LifecycleSettings
from tools.phase23_lifecycle.scenario import run_lifecycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument("--console-port", type=int, default=18765)
    args = parser.parse_args()
    result = run_lifecycle(LifecycleSettings(
        repository=args.repository.absolute(), output_root=args.output.absolute(),
        run_id=args.run_id, owner_ollama_url=args.ollama_url,
        model_ref=args.model, console_port=args.console_port,
    ))
    print(json.dumps({"passed": result["passed"], "output": str(args.output)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
