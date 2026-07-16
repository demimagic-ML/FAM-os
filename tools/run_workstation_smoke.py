"""Run the verified workload with full-workstation resource evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fam_os.scheduler import FULL_REFERENCE_WORKSTATION_PROFILE_ID
from tools.parity.composition import load_benchmark_composition
from tools.run_verified_parity import run_verified_parity
from tools.workstation.evidence import WorkstationEvidenceCollector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trusted-tests", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--effective-budget", type=Path, required=True)
    args = parser.parse_args()
    composition = load_benchmark_composition(args.profile, args.effective_budget)
    if composition.profile.profile_id != FULL_REFERENCE_WORKSTATION_PROFILE_ID:
        raise ValueError("workstation smoke requires full-reference-workstation")
    output, report = run_verified_parity(
        args.config,
        args.trusted_tests,
        args.output_dir,
        composition,
        WorkstationEvidenceCollector(),
    )
    print(
        json.dumps(
            {"output": str(output), "smoke_checks": report["smoke_checks"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
