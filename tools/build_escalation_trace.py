#!/usr/bin/env python3
"""Build one strict package- and budget-bound escalation trace."""

import argparse
import hashlib
import json
from pathlib import Path

from fam_os.experts import EscalationBudgetEvidence, EscalationTraceReport, ExpertRuntimeBinding
from fam_os.schemas import dumps_document, loads_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--trusted-tests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.raw_report.read_text())
    config = json.loads(args.config.read_text())
    binding = loads_document(args.binding.read_text())
    if not isinstance(binding, ExpertRuntimeBinding):
        raise ValueError("expert runtime binding required")
    budget_raw = raw["global_attempt_budget"]
    budget = EscalationBudgetEvidence(
        budget_raw["consumed_tokens"], budget_raw["consumed_wall_milliseconds"],
        budget_raw["repairs"], budget_raw["escalations"],
        tuple(budget_raw["reservation_ids"]),
    )
    examples = json.dumps(config["repair_examples"], sort_keys=True, separators=(",", ":"))
    attempts = raw["attempts"]
    report = EscalationTraceReport(
        f"escalation-{binding.expert_id}", config["economical_expert"],
        binding.artifact_ref, binding.expert_id, binding.expected_artifact_digest.value,
        tuple(item["kind"] for item in attempts),
        tuple(item["verification"]["status"] for item in attempts),
        "stable-toposort-v2", _digest(args.trusted_tests.read_bytes()),
        _digest(examples.encode()), 4000, budget, bool(raw["result"]["verified"]),
        _digest(args.raw_report.read_bytes()),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dumps_document(report) + "\n")
    print(json.dumps({"output": str(args.output), "verified": report.verified}, indent=2))


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    main()
