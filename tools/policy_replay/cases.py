"""Compose immutable replay cases from prior canonical scheduler evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fam_os.scheduler import (
    CacheEntryState,
    CachePolicyRequest,
    CacheTelemetryEntry,
    CacheTelemetrySnapshot,
    CacheTier,
    CacheTierPressure,
    DeterministicCacheRetentionPolicy,
)
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
ADMISSION = ROOT / "artifacts/scheduler/phase7.4/reference-admission-replay"
GPU = ROOT / "artifacts/scheduler/phase7.6/full-gpu-placement-canonical/gpu-report.json"
STORAGE = ROOT / "artifacts/scheduler/phase7.7/llama-storage-paging-canonical/storage-paging-evidence.json"
NPU = ROOT / "artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical/npu-investigation-report.json"


def admission_cases():
    for request_path in sorted(ADMISSION.glob("*.request.json")):
        decision_path = request_path.with_name(request_path.name.replace(".request.", ".decision."))
        yield request_path.name.removesuffix(".request.json"), _load(request_path), _load(decision_path)


def gpu_cases():
    report = _load(GPU)
    for index, evidence in enumerate(report.evidences, start=1):
        model = evidence.request.weight.runtime_artifact_id.replace(":", "-").replace("_", "-")
        yield f"gpu-{index}-{model}", evidence.request, evidence.decision


def cache_case():
    storage = _load(STORAGE)
    gpu = _load(GPU)
    npu = _load(NPU)
    source_digests = (_digest(STORAGE), _digest(GPU), _digest(NPU))
    page = storage.warm_trial.cache_after_load
    entries = [_page_entry(storage, page, source_digests[0])]
    entries.append(_provider_entry(storage, source_digests[0]))
    entries.extend(_accelerator_entries(gpu, source_digests[1]))
    entries.append(_npu_entry(npu, source_digests[2]))
    observed_at = max(page.observed_at, gpu.completed_at, npu.completed_at)
    snapshot = CacheTelemetrySnapshot(
        "cache-live-replay-20260716", 1, None, observed_at, tuple(entries), False,
    )
    pressure = CacheTierPressure(
        CacheTier.HOST_PAGE_CACHE, max(1, page.resident_bytes_upper_bound // 2)
    )
    request = CachePolicyRequest("cache-policy-live-1", snapshot, (pressure,), ())
    decision = DeterministicCacheRetentionPolicy().decide("cache-decision-live-1", request)
    return "cache-host-page-retention", request, decision


def _page_entry(storage, page, source_digest):
    return CacheTelemetryEntry(
        storage.artifact.artifact_id, CacheTier.HOST_PAGE_CACHE,
        CacheEntryState.WARM, storage.artifact.observed_file_bytes,
        page.resident_bytes_upper_bound, 1, 1, page.observed_at,
        storage.warm_trial.provider_load_seconds * 1000, True, source_digest,
    )


def _provider_entry(storage, source_digest):
    return CacheTelemetryEntry(
        storage.artifact.artifact_id, CacheTier.PROVIDER_WEIGHTS,
        CacheEntryState.COLD, storage.warm_trial.provider_resident_bytes,
        0, 1, 1, None, storage.warm_trial.provider_load_seconds * 1000,
        False, source_digest,
    )


def _accelerator_entries(gpu, source_digest):
    return tuple(CacheTelemetryEntry(
        item.request.weight.runtime_artifact_id, CacheTier.ACCELERATOR_WEIGHTS,
        CacheEntryState.COLD, item.provider_resident_bytes, 0, 1, 0,
        None, item.provider_load_seconds * 1000, False, source_digest,
    ) for item in gpu.evidences)


def _npu_entry(npu, source_digest):
    model_bytes = sum((NPU.parent / name).stat().st_size for name in (
        "routing-micro-expert.xml", "routing-micro-expert.bin"
    ))
    return CacheTelemetryEntry(
        npu.micro_expert.model_digest_sha256, CacheTier.NPU_COMPILED,
        CacheEntryState.COLD, model_bytes, 0, 1, 0, None,
        npu.micro_expert.compile_duration_ms, False, source_digest,
    )


def _load(path: Path):
    return loads_document(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
