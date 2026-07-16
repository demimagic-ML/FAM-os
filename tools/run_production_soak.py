#!/usr/bin/env python3
"""Run and persist the configurable Phase 14 production soak."""

import argparse
import json
from pathlib import Path

from fam_os.product.soak_runner import run_soak


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=float, default=86_400)
    parser.add_argument("--interval-seconds", type=float, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = args.output.parent / ".soak-work"
    report = run_soak(work, args.duration_seconds, args.interval_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    work.rmdir()
    print(json.dumps(report.to_dict(), sort_keys=True))
    raise SystemExit(not report.passed)


if __name__ == "__main__":
    main()
