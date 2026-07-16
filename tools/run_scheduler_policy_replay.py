#!/usr/bin/env python3
"""Replay canonical admission, GPU, and cache policies without current host state."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fam_os.scheduler import SchedulerPolicyReplayReport
from fam_os.schemas import encode_document
from tools.policy_replay.cases import admission_cases, cache_case, gpu_cases
from tools.policy_replay.engine import replay_case


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = (*admission_cases(), *gpu_cases(), cache_case())
    records = tuple(replay_case(case_id, request, expected, output) for case_id, request, expected in cases)
    report = SchedulerPolicyReplayReport(
        "scheduler-policy-replay-live-20260716", datetime.now(timezone.utc),
        records, all(item.matched for item in records),
    )
    _write(output / "policy-replay-report.json", encode_document(report))
    summary = {
        "schema_version": 1,
        "case_count": len(records),
        "policy_kinds": sorted({item.policy_kind.value for item in records}),
        "matched_count": sum(item.matched for item in records),
        "all_matched": report.all_matched,
        "current_host_state_consulted": any(item.current_host_state_consulted for item in records),
    }
    _write(output / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
