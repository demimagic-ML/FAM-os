#!/usr/bin/env python3
"""Build deterministic advisory expert-evolution proposals."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.experts.evolution_policy import (
    ExpertEvolutionPolicy, ExpertEvolutionReport, ExpertPerformanceSlice,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.fixture.read_text())
    slices = tuple(ExpertPerformanceSlice(**item) for item in raw["slices"])
    policy = ExpertEvolutionPolicy()
    proposals = (
        policy.split("general", slices),
        policy.merge("duplicate-a", "duplicate-b", slices),
        policy.retire("old", "new", slices),
    )
    report = ExpertEvolutionReport(
        "phase9.8-evolution-v1", tuple(raw["benchmark_ids"]),
        tuple(item for item in proposals if item is not None),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
