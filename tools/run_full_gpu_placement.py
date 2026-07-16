#!/usr/bin/env python3
"""Run full-profile GPU and split-offload placement evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fam_os.scheduler import FullWorkstationGpuReport
from fam_os.schemas import encode_document
from tools.gpu_workstation.workload import run_gpu_workload
from tools.parity.composition import load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11514")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    composition = load_benchmark_composition(args.profile, args.budget)
    service = ProfiledOllamaService(ProfiledServiceSettings(
        args.base_url, 600, composition, service_id="fam-full-gpu",
        readiness_seconds=30,
    ))
    started = datetime.now(timezone.utc)
    try:
        service.start()
        evidences, snapshots, final_loaded = run_gpu_workload(service, output)
    finally:
        service.stop()
    report = _report(service, started, evidences, snapshots, final_loaded)
    (output / "gpu-report.json").write_text(
        json.dumps(encode_document(report), indent=2, sort_keys=True) + "\n"
    )
    summary = _summary(report)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _report(service, started, evidences, snapshots, final_loaded):
    valid = tuple(item for item in snapshots if item is not None)
    maximum = lambda name: max(getattr(item, name) or 0 for item in valid)
    composition = service.settings.composition
    return FullWorkstationGpuReport(
        "full-gpu-live-20260716", started, datetime.now(timezone.utc),
        composition.profile.profile_id, composition.budget.budget_id,
        service.settings.service_id, evidences,
        maximum("memory_peak_bytes"), maximum("cpu_usage_microseconds"),
        maximum("io_read_bytes"), maximum("io_write_bytes"),
        service.lifecycle.status(service.settings.service_id).state.value,
        final_loaded,
    )


def _summary(report):
    return {
        "schema_version": 1,
        "run_id": report.run_id,
        "validation_profile_id": report.validation_profile_id,
        "service_memory_peak_bytes": report.service_memory_peak_bytes,
        "service_cpu_usage_microseconds": report.service_cpu_usage_microseconds,
        "service_io_read_bytes": report.service_io_read_bytes,
        "service_final_state": report.service_final_state,
        "placements": [
            {
                "model_ref": item.request.weight.runtime_artifact_id,
                "layers": [item.request.requested_accelerator_layers, item.request.model_layer_count],
                "host_compute_bytes": item.provider_host_compute_bytes,
                "accelerator_bytes": item.provider_accelerator_bytes,
                "load_seconds": item.provider_load_seconds,
                "effective_transfer_bytes_per_second": item.effective_transfer_bytes_per_second,
                "accelerator_memory_delta_bytes": item.accelerator_memory_delta_bytes,
            }
            for item in report.evidences
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
