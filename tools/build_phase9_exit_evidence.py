#!/usr/bin/env python3
"""Build Phase 9 exit evidence from checked artifacts."""

import json
from dataclasses import asdict
from pathlib import Path

from fam_os.experts.phase9_exit import Phase9ExitEvidence

ROOT = Path(__file__).parents[1]


def main():
    mixed = json.loads((ROOT / "artifacts/expert_fabric/phase9.1/mixed-verified-report.json").read_text())["payload"]
    results = mixed["results"]
    largest = tuple(item["case_id"] for item in results if item["expert_tier"] == "escalation")
    artifacts = tuple(f"phase9.{value}" for value in range(1, 9))
    evidence = Phase9ExitEvidence(
        "phase9-exit-v1", mixed["passed"], len(results), len(results) - len(largest),
        largest, artifacts, mixed["passed"] and len(results) - len(largest) > len(results) / 2,
    )
    output = ROOT / "artifacts/expert_fabric/phase9-exit.json"
    output.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
