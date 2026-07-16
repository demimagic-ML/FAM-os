"""Live constrained multi-expert workload helpers."""

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
    CpuBaselineExpertAttempt,
    DeterministicAdmissionPolicy,
    ExpertResidencyIdentity,
    ExpertResidencyService,
    LiveResourceSampler,
    ResidentWeightEstimate,
    ResidencyEvictionCoordinator,
    WeightEstimateSource,
    initial_cold_residency_catalog,
)
from fam_os.scheduler.admission_inputs import build_admission_request
from fam_os.scheduler.residency_repository import InMemoryExpertResidencyRepository
from fam_os.schemas import loads_document


EXECUTED = (
    ("expert.language.llama3.2-3b", "llama3.2:3b"),
    ("expert.code.qwen2.5-coder-7b", "qwen2.5-coder:7b"),
)
REJECTED = (
    ("expert.code.laguna-xs2-33b", "laguna-xs.2:q4_K_M"),
    ("expert.code.gemma4-26b", "gemma4:26b"),
)


def run_workload(service, output: Path):
    started = datetime.now(timezone.utc)
    entries, contexts = _inputs()
    identities = tuple(ExpertResidencyIdentity(expert, model) for expert, model in EXECUTED + REJECTED)
    repository = InMemoryExpertResidencyRepository()
    catalog = repository.initialize(initial_cold_residency_catalog(
        "cpu-baseline-residency", identities, started
    ))
    residency = ExpertResidencyService(repository)
    policy = DeterministicAdmissionPolicy()
    sampler = _sampler(service, output)
    observations = []
    attempts = []
    snapshots = []
    loaded_sets = []

    previous = _sample(sampler, observations, None)
    for expert_id, model_ref in EXECUTED:
        decision = _decision(policy, expert_id, previous, catalog, entries, contexts)
        response = service.runtime.chat(_request(model_ref))
        loaded = service.runtime.loaded_models()
        loaded_sets.append(tuple(sorted(item.model_ref for item in loaded)))
        catalog = residency.reconcile(loaded, datetime.now(timezone.utc), catalog.revision)
        model = next(item for item in loaded if item.model_ref == model_ref)
        attempts.append(CpuBaselineExpertAttempt(
            expert_id, model_ref, decision, True,
            hashlib.sha256(response.content.encode()).hexdigest(),
            model.resident_bytes, model.accelerator_bytes,
        ))
        snapshots.append(service.snapshot())
        previous = _sample(sampler, observations, previous)

    for expert_id, model_ref in REJECTED:
        decision = _decision(policy, expert_id, previous, catalog, entries, contexts)
        attempts.append(CpuBaselineExpertAttempt(
            expert_id, model_ref, decision, False, None, None, None
        ))
        previous = _sample(sampler, observations, previous)

    catalog, previous = _evict_all(
        residency, service.runtime, catalog, sampler, observations, previous
    )
    snapshots.append(service.snapshot())
    final_loaded = tuple(item.model_ref for item in service.runtime.loaded_models())
    concurrent = max(loaded_sets, key=lambda item: (len(item), item))
    return (
        started, tuple(observations), tuple(attempts), tuple(snapshots),
        concurrent, final_loaded,
    )


def _evict_all(residency, runtime, catalog, sampler, observations, previous):
    coordinator = ResidencyEvictionCoordinator(residency, runtime)
    for index, (expert_id, _) in enumerate(reversed(EXECUTED), 1):
        now = datetime.now(timezone.utc)
        catalog = coordinator.evict(
            expert_id, f"cpu-baseline-eviction-{index}", now,
            datetime.now(timezone.utc), catalog.revision,
        )
        previous = _sample(sampler, observations, previous)
    return catalog, previous


def _decision(policy, expert_id, observation, catalog, entries, contexts):
    entry = entries[expert_id]
    weight = ResidentWeightEstimate(
        expert_id, entry["runtime_artifact_id"], entry["resident_weight_bytes"],
        WeightEstimateSource.DECLARED_CONSERVATIVE,
        "artifact storage_bytes plus 10 percent weight-runtime expansion",
    )
    request = build_admission_request(
        f"cpu-baseline-admission.{expert_id}", expert_id, observation, catalog,
        weight, contexts[expert_id], {},
    )
    return policy.decide(f"cpu-baseline-decision.{expert_id}", request)


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
        lambda: f"cpu-baseline.{uuid4().hex}",
    )


def _sample(sampler, observations, previous):
    if previous is not None:
        time.sleep(0.25)
    current = sampler.sample(previous)
    observations.append(current)
    return current


def _request(model_ref):
    return InferenceRequest(
        model_ref,
        (InferenceMessage(MessageRole.USER, "Reply with the single word ready."),),
        512, 8, keep_alive="10m",
    )


def _inputs():
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "configs/admission/reference-weight-estimates.json").read_text())
    entries = {item["expert_id"]: item for item in config["entries"]}
    context_root = root / "artifacts/scheduler/phase7.2/reference-context-estimates"
    contexts = {
        expert: loads_document((context_root / f"context.{expert.removeprefix('expert.')}.estimate.json").read_text())
        for expert, _ in EXECUTED + REJECTED
    }
    return entries, contexts
