#!/usr/bin/env python3
"""Run the complete Phase 19 gate from a fresh signed installation."""

import argparse
import json
from pathlib import Path

from tools.phase19_exit.scenario import run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--code", type=Path, default=Path("/usr/bin/code"))
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/product/phase19/phase19-exit.json"),
    )
    args = parser.parse_args()
    report = run(
        args.repository.resolve(), args.code.resolve(), args.ollama_url,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
