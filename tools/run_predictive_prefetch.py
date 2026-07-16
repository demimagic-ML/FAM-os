#!/usr/bin/env python3
"""Predict, admit, and verify one bounded model-artifact prefetch."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux.bounded_prefetch import BoundedFilePrefetcher
from fam_os.adapters.linux.model_cache import MmapPageCacheObserver, OllamaModelBlobResolver
from fam_os.scheduler import (
    ArtifactAccessSequence,
    CacheEntryState,
    CacheTelemetryEntry,
    CacheTelemetrySnapshot,
    CacheTier,
    DeterministicPrefetchAdmissionPolicy,
    DeterministicTransitionPredictor,
    PredictivePrefetchReport,
    PrefetchCandidate,
    PrefetchExecutionEvidence,
    PrefetchPolicyRequest,
    PrefetchPredictionRequest,
    PrefetchResourceBudget,
)
from fam_os.schemas import encode_document, loads_document
from tools.storage_paging.owned_store import clone_model_store


ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = Path("/usr/share/ollama/.ollama/models")
CPU_REPORT = ROOT / "artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/baseline-report.json"
GPU_REPORT = ROOT / "artifacts/scheduler/phase7.6/full-gpu-placement-canonical/gpu-report.json"
PREFETCH_BYTES = 32 * 1024**2
OS_RESERVE_BYTES = 12 * 1024**3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    resolver = OllamaModelBlobResolver(MODEL_ROOT)
    prediction_request = _prediction_request(resolver)
    prediction = DeterministicTransitionPredictor().predict(
        "prefetch-prediction-live-1", prediction_request
    )
    if prediction is None:
        raise RuntimeError("canonical history did not meet the prefetch threshold")
    captured = _execute_owned_prefetch(prediction, resolver)
    snapshot, admitted_request, admitted, values = captured
    guard_request = replace(
        admitted_request,
        request_id="prefetch-waste-guard-live-1",
        budget=replace(admitted_request.budget, current_waste_bytes=40 * 1024**2),
    )
    guard = DeterministicPrefetchAdmissionPolicy().decide(
        "prefetch-waste-guard-decision-live-1", guard_request
    )
    execution = PrefetchExecutionEvidence(
        "prefetch-execution-live-1", prediction, admitted,
        values[0], values[1], PREFETCH_BYTES, values[2].bytes_read,
        values[3].bytes_read, values[2].physical_read_bytes,
        values[3].physical_read_bytes, values[4], values[5],
        values[2].digest_sha256, values[3].digest_sha256, True, True,
    )
    report = PredictivePrefetchReport(
        "predictive-prefetch-live-20260716", prediction_request, prediction,
        admitted_request, admitted, execution, guard_request, guard,
    )
    _write(output / "predictive-prefetch-report.json", encode_document(report))
    _write(output / "summary.json", _summary(report, snapshot))
    print(json.dumps(_summary(report, snapshot), indent=2, sort_keys=True))
    return 0


def _prediction_request(resolver):
    cpu = loads_document(CPU_REPORT.read_text(encoding="utf-8"))
    gpu = loads_document(GPU_REPORT.read_text(encoding="utf-8"))
    cpu_refs = tuple(item.model_ref for item in cpu.attempts if item.inference_executed)
    gpu_refs = tuple(item.request.weight.runtime_artifact_id for item in gpu.evidences)
    sequences = (
        _sequence("cpu-baseline", cpu.completed_at, cpu_refs, CPU_REPORT, resolver),
        _sequence("gpu-placement", gpu.completed_at, gpu_refs, GPU_REPORT, resolver),
    )
    llama = resolver.resolve("llama3.2:3b")
    qwen = resolver.resolve("qwen2.5-coder:7b")
    candidate = PrefetchCandidate(
        qwen.artifact_id, CacheTier.HOST_PAGE_CACHE, qwen.declared_bytes,
        PREFETCH_BYTES, 1800.0,
    )
    return PrefetchPredictionRequest(
        "prefetch-prediction-request-live-1", llama.artifact_id,
        datetime.now(timezone.utc), (candidate,), sequences, 2, 1.0, 600,
    )


def _sequence(identifier, observed_at, refs, source, resolver):
    artifacts = tuple(resolver.resolve(model_ref).artifact_id for model_ref in refs)
    return ArtifactAccessSequence(
        identifier, observed_at, artifacts, hashlib.sha256(source.read_bytes()).hexdigest()
    )


def _execute_owned_prefetch(prediction, resolver):
    with tempfile.TemporaryDirectory(prefix="fam-prefetch-") as directory:
        model_root = clone_model_store(MODEL_ROOT, Path(directory) / "models", "qwen2.5-coder:7b")
        blob = OllamaModelBlobResolver(model_root).resolve("qwen2.5-coder:7b")
        observer = MmapPageCacheObserver(model_root)
        observer.evict(blob)
        before = observer.observe(blob, "prefetch-cache-before")
        snapshot = _snapshot(prediction, before)
        request = _policy_request(prediction, snapshot)
        decision = DeterministicPrefetchAdmissionPolicy().decide(
            "prefetch-admission-decision-live-1", request
        )
        started = datetime.now(timezone.utc)
        prefetcher = BoundedFilePrefetcher(model_root)
        prefetched = prefetcher.read_range(blob.path, PREFETCH_BYTES)
        after = observer.observe(blob, "prefetch-cache-after")
        demanded = prefetcher.read_range(blob.path, PREFETCH_BYTES)
        completed = datetime.now(timezone.utc)
        values = (started, completed, prefetched, demanded,
                  before.resident_bytes_upper_bound, after.resident_bytes_upper_bound)
    return snapshot, request, decision, values


def _snapshot(prediction, observation):
    candidate = prediction.candidate
    entry = CacheTelemetryEntry(
        candidate.artifact_id, candidate.tier, CacheEntryState.COLD,
        candidate.artifact_bytes, 0, 0, 0, None,
        candidate.expected_reload_cost_ms, False,
        candidate.artifact_id.removeprefix("ollama-blob:"),
    )
    return CacheTelemetrySnapshot(
        "prefetch-cache-snapshot-live-1", 1, None, observation.observed_at,
        (entry,), False,
    )


def _policy_request(prediction, snapshot):
    available = _mem_available_bytes()
    budget = PrefetchResourceBudget(
        PREFETCH_BYTES, PREFETCH_BYTES, 64 * 1024**2, available,
        OS_RESERVE_BYTES, 1, 64 * 1024**2, 0,
    )
    return PrefetchPolicyRequest(
        "prefetch-admission-request-live-1", prediction, snapshot, budget,
        datetime.now(timezone.utc), 0, False,
    )


def _mem_available_bytes() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable is unavailable")


def _summary(report, snapshot):
    execution = report.execution
    return {
        "schema_version": 1, "prediction_confidence": report.prediction.confidence,
        "transition_observations": report.prediction.transition_observations,
        "prefetch_bytes": execution.prefetched_bytes,
        "prefetch_physical_read_bytes": execution.prefetch_physical_read_bytes,
        "demand_physical_read_bytes": execution.demand_physical_read_bytes,
        "cache_bytes_before": execution.cache_bytes_before,
        "cache_bytes_after": execution.cache_bytes_after,
        "waste_guard_status": report.waste_guard_decision.status.value,
        "waste_guard_reasons": report.waste_guard_decision.reasons,
        "os_reserve_bytes": report.admitted_request.budget.operating_system_reserve_bytes,
        "temporary_artifact_removed": execution.temporary_artifact_removed,
        "snapshot_complete": snapshot.current_host_state_complete,
    }


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
