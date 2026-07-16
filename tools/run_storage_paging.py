#!/usr/bin/env python3
"""Capture strict SSD, mmap-cache, cold/warm load, and I/O evidence."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from fam_os.scheduler import StoragePagingEvidence
from fam_os.schemas import encode_document
from tools.parity.composition import load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings
from tools.storage_paging.workload import run_storage_trials
from tools.storage_paging.owned_store import clone_model_store


SOURCE_MODEL_ROOT = Path("/usr/share/ollama/.ollama/models")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11515")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    composition = load_benchmark_composition(args.profile, args.budget)
    with tempfile.TemporaryDirectory(prefix="fam-storage-paging-") as directory:
        model_root = clone_model_store(
            SOURCE_MODEL_ROOT, Path(directory) / "models", "llama3.2:3b"
        )
        service = ProfiledOllamaService(ProfiledServiceSettings(
            args.base_url, 300, composition, service_id="fam-storage-paging",
            models_path=str(model_root), readiness_seconds=30,
        ))
        try:
            service.start()
            result = run_storage_trials(service, model_root)
        finally:
            service.stop()
        artifact, budget, before, cold, warm, final_loaded = result
        final_state = service.lifecycle.status(service.settings.service_id).state.value
    evidence = StoragePagingEvidence(
        "storage-paging-live-20260716", artifact, budget, before, cold, warm,
        final_state, final_loaded,
    )
    (output / "storage-paging-evidence.json").write_text(
        json.dumps(encode_document(evidence), indent=2, sort_keys=True) + "\n"
    )
    summary = _summary(evidence)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _summary(evidence):
    return {
        "schema_version": 1,
        "model_ref": evidence.artifact.model_ref,
        "artifact_id": evidence.artifact.artifact_id,
        "artifact_bytes": evidence.artifact.observed_file_bytes,
        "storage_medium": evidence.artifact.storage_medium.value,
        "path_disclosed": evidence.artifact.path_disclosed,
        "kernel_bandwidth_controller_available": evidence.budget.kernel_bandwidth_controller_available,
        "maximum_physical_read_bytes": evidence.budget.maximum_physical_read_bytes,
        "cache_before_eviction_bytes": evidence.cache_before_eviction.resident_bytes_upper_bound,
        "cold_cache_before_bytes": evidence.cold_trial.cache_before_load.resident_bytes_upper_bound,
        "cold_cache_after_bytes": evidence.cold_trial.cache_after_load.resident_bytes_upper_bound,
        "cold_physical_read_bytes": evidence.cold_trial.physical_read_bytes,
        "cold_logical_read_bytes": evidence.cold_trial.logical_read_bytes,
        "cold_load_seconds": evidence.cold_trial.provider_load_seconds,
        "warm_cache_before_bytes": evidence.warm_trial.cache_before_load.resident_bytes_upper_bound,
        "warm_physical_read_bytes": evidence.warm_trial.physical_read_bytes,
        "warm_logical_read_bytes": evidence.warm_trial.logical_read_bytes,
        "warm_load_seconds": evidence.warm_trial.provider_load_seconds,
        "service_final_state": evidence.service_final_state,
    }


if __name__ == "__main__":
    raise SystemExit(main())
