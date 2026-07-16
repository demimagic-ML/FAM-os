#!/usr/bin/env python3
"""Run the real 16 GiB CPU-only multi-expert scheduler baseline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fam_os.scheduler import CPU_ONLY_ENVIRONMENT, CpuOnlyBaselineReport
from fam_os.schemas import encode_document
from tools.cpu_baseline.workload import run_workload
from tools.parity.composition import load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11513")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    composition = load_benchmark_composition(args.profile, args.budget)
    settings = ProfiledServiceSettings(
        args.base_url, 300, composition, service_id="fam-cpu-baseline",
        readiness_seconds=30,
    )
    service = ProfiledOllamaService(settings)
    try:
        service.start()
        result = run_workload(service, output)
    finally:
        service.stop()
    report = _report(service, datetime.now(timezone.utc), result)
    (output / "baseline-report.json").write_text(
        json.dumps(encode_document(report), indent=2, sort_keys=True) + "\n"
    )
    summary = _summary(report)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _report(service, completed, result):
    started, observations, attempts, snapshots, concurrent, final_loaded = result
    composition = service.settings.composition
    budget = composition.budget
    defined = service.definition()
    valid = tuple(item for item in snapshots if item is not None)
    memory_peak = max(item.memory_peak_bytes or 0 for item in valid)
    swap_peak = max(item.swap_current_bytes or 0 for item in valid)
    cpu_usage = max(item.cpu_usage_microseconds or 0 for item in valid)
    oom_kills = max(item.event_count("oom_kill") or 0 for item in valid)
    quota = defined.limits.cpu_quota_percent / 100
    return CpuOnlyBaselineReport(
        "cpu-baseline-live-20260716", started, completed,
        composition.profile.profile_id, budget.budget_id, service.settings.service_id,
        defined.limits.memory_max_bytes, budget.memory.scheduler_limit_bytes,
        budget.memory.reserved_headroom_bytes, memory_peak,
        defined.limits.swap_max_bytes, swap_peak, quota, cpu_usage,
        CPU_ONLY_ENVIRONMENT, observations, attempts, concurrent, oom_kills,
        service.lifecycle.status(service.settings.service_id).state.value, final_loaded,
    )


def _summary(report):
    return {
        "schema_version": 1,
        "run_id": report.run_id,
        "validation_profile_id": report.validation_profile_id,
        "memory_limit_bytes": report.service_memory_limit_bytes,
        "memory_peak_bytes": report.service_memory_peak_bytes,
        "operating_system_reserve_bytes": report.operating_system_reserve_bytes,
        "swap_peak_bytes": report.service_swap_peak_bytes,
        "cpu_quota_cores": report.service_cpu_quota_cores,
        "cpu_usage_microseconds": report.service_cpu_usage_microseconds,
        "observation_count": len(report.observations),
        "maximum_concurrent_loaded_model_refs": list(
            report.maximum_concurrent_loaded_model_refs
        ),
        "attempts": [
            {
                "model_ref": item.model_ref,
                "admission": item.decision.status.value,
                "executed": item.inference_executed,
                "resident_bytes": item.provider_resident_bytes,
                "accelerator_bytes": item.provider_accelerator_bytes,
            }
            for item in report.attempts
        ],
        "oom_kill_count": report.oom_kill_count,
        "service_final_state": report.service_final_state,
    }


if __name__ == "__main__":
    raise SystemExit(main())
