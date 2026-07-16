"""Assemble the Phase 1 parity gate from final machine-readable artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.parity.checks import checks_payload, routing_checks, verified_checks
from tools.parity.report_writer import captured_at, write_report


def build_phase1_parity_report(
    routing_path: Path,
    policy_path: Path,
    verified_path: Path,
    output_dir: Path,
    fam_test_count: int,
    parent_test_count: int,
    diagnostic_paths: tuple[Path, ...] = (),
) -> tuple[Path, dict[str, Any]]:
    routing = _read(routing_path)
    policy = _read(policy_path)
    verified = _read(verified_path)
    checks = routing_checks(routing) + verified_checks(verified)
    all_checks = checks_payload(checks) + _migration_checks(
        policy, fam_test_count, parent_test_count
    )
    payload = {
        "schema_version": 1,
        "report": "phase1-controlled-migration-parity",
        "captured_at": captured_at(),
        "artifacts": {
            "routing": str(routing_path.resolve()),
            "policy_comparison": str(policy_path.resolve()),
            "verified_escalation": str(verified_path.resolve()),
        },
        "diagnostic_artifacts": [str(path.resolve()) for path in diagnostic_paths],
        "historical_references": {
            "routing": "artifacts/benchmarks/kernel-routing-20260716-095900.json",
            "policy": "artifacts/benchmarks/expert-activation-20260716-102137.json",
            "verified": "artifacts/benchmarks/verified-task-20260716-104128.json",
        },
        "test_counts": {"fam_os": fam_test_count, "parent": parent_test_count},
        "checks": all_checks,
        "passed": all(item["passed"] for item in all_checks),
        "current_measurements": _measurements(routing, policy, verified),
    }
    output = write_report(output_dir, "phase1-parity", payload)
    return output, payload


def _migration_checks(
    policy: dict[str, Any],
    fam_test_count: int,
    parent_test_count: int,
) -> list[dict[str, object]]:
    return [
        {"name": "fam_os_tests", "passed": fam_test_count > 0, "detail": str(fam_test_count)},
        {
            "name": "parent_tests",
            "passed": parent_test_count > 0,
            "detail": str(parent_test_count),
        },
        {
            "name": "policy_comparison",
            "passed": policy["passed"] is True,
            "detail": str(policy["passed"]),
        },
    ]


def _measurements(
    routing: dict[str, Any],
    policy: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    summary = routing["models"][0]["summary"]
    policies = policy["policies"]
    return {
        "routing": summary,
        "policies": {
            name: {
                "memory_peak_bytes": item["resources"]["memory_peak_bytes"],
                "wall_seconds": item["expert_metrics"]["wall_seconds"],
                "load_seconds": item["expert_metrics"]["load_seconds"],
                "generation_tokens_per_second": item["expert_metrics"][
                    "generation_tokens_per_second"
                ],
            }
            for name, item in policies.items()
        },
        "verified": {
            "status": verified["status"],
            "attempt_kinds": [attempt["kind"] for attempt in verified["attempts"]],
            "memory_peak_bytes": verified["resources"]["memory_peak_bytes"],
        },
    }


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"parity artifact must be a JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--verified", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, action="append", default=[])
    parser.add_argument("--fam-tests", type=int, required=True)
    parser.add_argument("--parent-tests", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output, report = build_phase1_parity_report(
        args.routing,
        args.policy,
        args.verified,
        args.output_dir,
        args.fam_tests,
        args.parent_tests,
        tuple(args.diagnostic),
    )
    print(json.dumps({"output": str(output), "passed": report["passed"]}, indent=2))


if __name__ == "__main__":
    main()
