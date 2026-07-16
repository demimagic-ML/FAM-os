"""Execute and measure full-workstation GPU placements one at a time."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.cgroup import CgroupV2ResourceObserver
from fam_os.adapters.linux import (
    CacheDirectory,
    DirectoryStorageRuntimeObserver,
    NvidiaAcceleratorRuntimeObserver,
)
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole
from fam_os.scheduler import (
    DeterministicGpuPlacementPolicy,
    GpuPlacementEvidence,
    GpuPlacementRequest,
    LiveResourceSampler,
    ResidentWeightEstimate,
    WeightEstimateSource,
)
from fam_os.schemas import dumps_document, loads_document


def run_gpu_workload(service, output: Path):
    config, weights, contexts = _inputs()
    sampler = _sampler(service, output)
    policy = DeterministicGpuPlacementPolicy()
    previous = sampler.sample()
    evidences = []
    snapshots = []
    for index, model in enumerate(config["models"], 1):
        request = _placement_request(index, model, previous, weights, contexts, config)
        decision = policy.decide(f"gpu-decision-{index}", request)
        if decision.status.value != "admitted":
            raise RuntimeError(f"full profile rejected {model['model_ref']}: {decision.reason_codes}")
        response = service.runtime.chat(_inference_request(model))
        loaded = service.runtime.loaded_models()
        provider = next(item for item in loaded if item.model_ref == model["model_ref"])
        time.sleep(0.25)
        after = sampler.sample(previous)
        snapshot = service.snapshot()
        evidence = _evidence(index, request, decision, after, provider, response, snapshot)
        evidences.append(evidence)
        snapshots.append(snapshot)
        _write(output / f"{index}-{_slug(model['model_ref'])}.json", evidence)
        service.runtime.unload(model["model_ref"])
        time.sleep(0.25)
        previous = sampler.sample(after)
    return tuple(evidences), tuple(snapshots), tuple(
        item.model_ref for item in service.runtime.loaded_models()
    )


def _placement_request(index, model, observation, weights, contexts, config):
    expert_id = model["expert_id"]
    entry = weights[expert_id]
    weight = ResidentWeightEstimate(
        expert_id, model["model_ref"], entry["resident_weight_bytes"],
        WeightEstimateSource.DECLARED_CONSERVATIVE,
        "artifact storage_bytes plus 10 percent weight-runtime expansion",
    )
    return GpuPlacementRequest(
        f"gpu-request-{index}", expert_id, observation, weight,
        contexts[expert_id], config["accelerator_device_id"],
        model["model_layer_count"], model["requested_accelerator_layers"],
        config["main_accelerator_index"],
    )


def _inference_request(model):
    return InferenceRequest(
        model["model_ref"],
        (InferenceMessage(MessageRole.USER, "Reply with the single word ready."),),
        5120, 8, keep_alive="10m",
        accelerator_layer_count=model["requested_accelerator_layers"],
        main_accelerator_index=0,
    )


def _evidence(index, request, decision, after, provider, response, snapshot):
    if provider.resident_bytes is None or provider.accelerator_bytes is None:
        raise RuntimeError("provider omitted split residency measurements")
    load_seconds = response.metrics.load_seconds
    if load_seconds <= 0:
        raise RuntimeError("provider omitted positive load duration")
    before_gpu = _gpu_current(request.observation, request.accelerator_device_id)
    after_gpu = _gpu_current(after, request.accelerator_device_id)
    return GpuPlacementEvidence(
        f"gpu-evidence-{index}", request, decision, after,
        provider.resident_bytes, provider.accelerator_bytes,
        provider.resident_bytes - provider.accelerator_bytes,
        load_seconds, provider.accelerator_bytes / load_seconds,
        0 if snapshot is None else snapshot.memory_peak_bytes or 0,
        max(0, after_gpu - before_gpu), True, provider.accelerator_bytes > 0,
        hashlib.sha256(response.content.encode()).hexdigest(),
    )


def _gpu_current(observation, device_id):
    return next(
        item.current_bytes or 0 for item in observation.accelerators
        if item.device_id == device_id
    )


def _sampler(service, output):
    runner = SubprocessCommandRunner()
    budget = service.settings.composition.budget
    cache = DirectoryStorageRuntimeObserver(tuple(
        CacheDirectory(item.storage_id, output) for item in budget.storage
    ))
    return LiveResourceSampler(
        budget, CgroupV2ResourceObserver(service.lifecycle),
        NvidiaAcceleratorRuntimeObserver(runner), cache,
        service.settings.service_id, (), lambda: datetime.now(timezone.utc),
        lambda: f"gpu-workstation.{uuid4().hex}",
    )


def _inputs():
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "configs/placement/full-workstation-gpu.json").read_text())
    weight_config = json.loads((root / "configs/admission/reference-weight-estimates.json").read_text())
    weights = {item["expert_id"]: item for item in weight_config["entries"]}
    context_root = root / "artifacts/scheduler/phase7.2/reference-context-estimates"
    contexts = {
        model["expert_id"]: loads_document((context_root / f"context.{model['expert_id'].removeprefix('expert.')}.estimate.json").read_text())
        for model in config["models"]
    }
    return config, weights, contexts


def _write(path, value):
    path.write_text(dumps_document(value) + "\n", encoding="utf-8")


def _slug(value):
    return value.replace(":", "-").replace(".", "-")
