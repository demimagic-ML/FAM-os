"""Run all three historical residency policies in fresh profiled services."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.parity.checks import (
    activation_checks,
    checks_payload,
    policy_comparison_checks,
)
from tools.parity.composition import BenchmarkComposition, load_benchmark_composition
from tools.parity.report_writer import captured_at, write_report
from tools.run_activation_parity import run_activation_parity


def run_policy_parity(
    config_paths: tuple[Path, ...],
    output_dir: Path,
    composition: BenchmarkComposition,
) -> tuple[Path, dict[str, Any]]:
    if len(config_paths) != 3:
        raise ValueError("policy parity requires exactly three historical configurations")
    reports: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, str] = {}
    for config_path in config_paths:
        output, report = run_activation_parity(config_path, output_dir, composition)
        policy = str(report["policy"])
        reports[policy] = report
        artifacts[policy] = str(output.resolve())
    checks = tuple(
        check for report in reports.values() for check in activation_checks(report)
    ) + policy_comparison_checks(reports)
    payload = {
        "schema_version": 1,
        "benchmark": "phase1-policy-parity",
        "captured_at": captured_at(),
        "constraints": composition.constraints_payload(),
        "profile_source": str(composition.profile_path) if composition.profile_path else None,
        "budget_source": str(composition.budget_path) if composition.budget_path else None,
        "artifacts": artifacts,
        "policies": {name: _summary(report) for name, report in reports.items()},
        "checks": checks_payload(checks),
        "passed": all(check.passed for check in checks),
    }
    output = write_report(output_dir, "policy-parity", payload)
    return output, payload


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "context_tokens": report["context_tokens"],
        "evict_kernel_before_expert": report["evict_kernel_before_expert"],
        "expert_metrics": report["expert_metrics"],
        "resources": report["resources"],
        "loaded_after_expert": report["loaded_after_expert"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--effective-budget", type=Path, required=True)
    args = parser.parse_args()
    composition = load_benchmark_composition(args.profile, args.effective_budget)
    output, report = run_policy_parity(
        tuple(args.config), args.output_dir, composition
    )
    print(json.dumps({"output": str(output), "passed": report["passed"]}, indent=2))


if __name__ == "__main__":
    main()
