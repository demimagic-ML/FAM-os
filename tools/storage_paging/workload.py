"""Real cold/warm Ollama model paging and process-I/O workload."""

from __future__ import annotations

import time
from pathlib import Path

from fam_os.adapters.linux.model_cache import (
    MmapPageCacheObserver,
    OllamaModelBlobResolver,
)
from fam_os.adapters.linux.process_io import CgroupProcessIoObserver
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole
from fam_os.scheduler import (
    LoadCacheState,
    ModelLoadIoBudget,
    ModelLoadIoTrial,
    ModelStorageArtifact,
    StorageMedium,
)


MODEL_REF = "llama3.2:3b"
def run_storage_trials(service, model_root: Path):
    blob = OllamaModelBlobResolver(model_root).resolve(MODEL_REF)
    cache = MmapPageCacheObserver(model_root)
    artifact = ModelStorageArtifact(
        blob.artifact_id, blob.model_ref, blob.digest_sha256,
        blob.declared_bytes, blob.path.stat().st_size, "storage-root",
        StorageMedium.NVME, "ext4", True, False, True,
    )
    budget = ModelLoadIoBudget(
        "io-budget.llama3.2-3b", artifact.artifact_id,
        artifact.observed_file_bytes * 2, 128 * 1024**2,
        1_000_000_000, 256_000_000, False, True,
    )
    _warm_cache(blob.path)
    before_eviction = cache.observe(blob, "cache-before-eviction")
    cache.evict(blob)
    cold_before = _await_eviction(cache, blob, before_eviction)
    cold = _trial(
        service, cache, blob, budget, LoadCacheState.COLD,
        cold_before, True,
    )
    warm_before = cache.observe(blob, "warm-cache-before-load")
    warm = _trial(
        service, cache, blob, budget, LoadCacheState.WARM,
        warm_before, False,
    )
    return artifact, budget, before_eviction, cold, warm, tuple(
        item.model_ref for item in service.runtime.loaded_models()
    )


def _trial(service, cache, blob, budget, state, before_cache, eviction):
    control_group = service.lifecycle.control_group(service.settings.service_id)
    if not control_group:
        raise RuntimeError("storage trial service cgroup is unavailable")
    observer = CgroupProcessIoObserver()
    before_io = observer.observe(control_group)
    response = service.runtime.chat(_request())
    provider = next(
        item for item in service.runtime.loaded_models() if item.model_ref == MODEL_REF
    )
    after_io = observer.observe(control_group)
    after_cache = cache.observe(blob, f"{state.value}-cache-after-load")
    snapshot = service.snapshot()
    service.runtime.unload(MODEL_REF)
    physical_read = max(0, after_io.physical_read_bytes - before_io.physical_read_bytes)
    physical_write = max(0, after_io.physical_write_bytes - before_io.physical_write_bytes)
    logical_read = max(0, after_io.logical_read_bytes - before_io.logical_read_bytes)
    if physical_read > budget.maximum_physical_read_bytes:
        raise RuntimeError("model load exceeded cumulative physical read budget")
    if physical_write > budget.maximum_physical_write_bytes:
        raise RuntimeError("model load exceeded cumulative physical write budget")
    effective = eviction and before_cache.resident_fraction < 0.25
    return ModelLoadIoTrial(
        f"{state.value}-load", state, before_cache, after_cache,
        physical_read, physical_write, logical_read, response.metrics.load_seconds,
        provider.resident_bytes or 0,
        0 if snapshot is None else snapshot.memory_peak_bytes or 0,
        eviction, effective, True,
    )


def _request():
    return InferenceRequest(
        MODEL_REF,
        (InferenceMessage(MessageRole.USER, "Reply with the single word ready."),),
        2048, 8, keep_alive="5m", accelerator_layer_count=0,
    )


def _warm_cache(path):
    with path.open("rb", buffering=0) as source:
        while source.read(8 * 1024**2):
            pass


def _await_eviction(cache, blob, before):
    current = cache.observe(blob, "cold-cache-before-load")
    deadline = time.monotonic() + 5
    while current.resident_page_count >= before.resident_page_count and time.monotonic() < deadline:
        time.sleep(0.1)
        current = cache.observe(blob, "cold-cache-before-load")
    if current.resident_fraction >= 0.25:
        raise RuntimeError("model cache eviction did not establish a cold artifact")
    return current
