"""Representative live scheduler schema values."""

from dataclasses import replace
from datetime import timedelta

from fam_os.scheduler import (
    ExpertUseObservation,
    LocalExpertFrequencyLearner,
    AdmissionRequest,
    AdmissionDecision,
    AdmissionStatus,
    CPU_ONLY_ENVIRONMENT,
    CpuBaselineExpertAttempt,
    CpuOnlyBaselineReport,
    DeterministicAdmissionPolicy,
    DeterministicGpuPlacementPolicy,
    GpuPlacementEvidence,
    GpuPlacementRequest,
    FullWorkstationGpuReport,
    ArtifactCacheObservation,
    LoadCacheState,
    ModelLoadIoBudget,
    ModelLoadIoTrial,
    ModelStorageArtifact,
    StoragePagingEvidence,
    ContextMemoryEstimator,
    ContextMemoryModelProfile,
    ContextMemoryReservation,
    ContextMemoryStrategy,
    ContextProfileSource,
    ResidentWeightEstimate,
    WeightEstimateSource,
    ExpertResidencyIdentity,
    initial_cold_residency_catalog,
    LiveAcceleratorAvailability,
    LiveCpuAvailability,
    LiveMemoryAvailability,
    LiveStorageAvailability,
    ManagedServiceUsage,
    ObservationStatus,
    SchedulerResourceObservation,
    StorageMedium,
    NpuHardwareEvidence,
    NpuInvestigationOutcome,
    NpuInvestigationReport,
    NpuMicroExpertEvidence,
    NpuRuntimeEvidence,
    CACHE_POLICY_VERSION,
    CacheEntryState,
    CachePolicyRequest,
    CacheTelemetryEntry,
    CacheTelemetrySnapshot,
    CacheTierPressure,
    DeterministicCacheRetentionPolicy,
    SchedulerPolicyKind,
    SchedulerPolicyReplayRecord,
    SchedulerPolicyReplayReport,
    ArtifactAccessSequence,
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
from tests.contract.schema_application_fixtures import NOW
from tests.contract.schema_configuration_fixtures import composed_configuration


def live_resource_observation() -> SchedulerResourceObservation:
    budget = composed_configuration().budget
    gpu = budget.accelerators[0]
    storage = budget.storage[0]
    return SchedulerResourceObservation(
        "live-1", 1, None, NOW, budget.budget_id, budget.inventory_id,
        budget.validation_profile.profile_id, "fam.slice", ObservationStatus.BASELINE,
        LiveCpuAvailability(budget.cpu.scheduler_quota_cores, None, None, None, None, 10),
        LiveMemoryAvailability(
            budget.memory.effective_limit_bytes, budget.memory.scheduler_limit_bytes,
            budget.memory.reserved_headroom_bytes, 1_024,
            budget.memory.scheduler_limit_bytes - 1_024,
            budget.memory.cgroup_limit_bytes, 0, 0, True,
        ),
        (LiveAcceleratorAvailability(
            gpu.device_id, gpu.placement_allowed, gpu.scheduler_memory_limit_bytes,
            0, gpu.scheduler_memory_limit_bytes,
        ),),
        (LiveStorageAvailability(
            storage.storage_id, storage.scheduler_cache_limit_bytes, 0,
            storage.scheduler_cache_limit_bytes,
        ),),
        (ManagedServiceUsage("fam-ollama", 512, 1_024, 10, 0),),
    )


def scheduler_schema_values() -> tuple[object, ...]:
    profile = ContextMemoryModelProfile(
        "context.qwen", "expert.code.qwen", "qwen:7b", "qwen2",
        ContextMemoryStrategy.AUTOREGRESSIVE_KV, 8_192, 28, 3_584, 28,
        4, 128, 128, 2, 256 * 1024**2, 64 * 1024**2, 2_500,
        ContextProfileSource.OBSERVED_METADATA,
        ("kv_cache.scalar_bytes_policy",),
    )
    reservation = ContextMemoryReservation("reservation-1", profile.profile_id, 2_048, 512)
    estimate = ContextMemoryEstimator().estimate("estimate-1", profile, reservation)
    residency = initial_cold_residency_catalog(
        "residency-1", (ExpertResidencyIdentity("expert.qwen", "qwen:7b"),), NOW
    )
    observation = live_resource_observation()
    admission = AdmissionRequest(
        "admission-1", observation.observation_id, observation.status,
        observation.memory.scope_authoritative,
        observation.memory.available_for_new_bytes, residency.catalog_id,
        residency.revision, "expert.qwen", residency.records[0].state,
        ResidentWeightEstimate(
            "expert.qwen", "qwen:7b", 5_000_000_000,
            WeightEstimateSource.DECLARED_CONSERVATIVE, "fixture weight bound",
        ),
        estimate.estimate_id, estimate.total_context_bytes,
        estimate.model_resident_bytes_excluded, (),
    )
    decision = DeterministicAdmissionPolicy().decide("decision-1", admission)
    gpu_request = GpuPlacementRequest(
        "gpu-request-1", "expert.qwen", observation,
        ResidentWeightEstimate(
            "expert.qwen", "qwen:7b", 5_000_000_000,
            WeightEstimateSource.DECLARED_CONSERVATIVE, "fixture weight bound",
        ),
        estimate, "gpu-0", 28, 14, 0,
    )
    gpu_decision = DeterministicGpuPlacementPolicy().decide(
        "gpu-decision-1", gpu_request
    )
    gpu_after = replace(
        observation, observation_id="gpu-live-2", sequence=2,
        previous_observation_id=observation.observation_id,
        observed_at=NOW + timedelta(seconds=1), status=ObservationStatus.COMPLETE,
        cpu=replace(
            observation.cpu, interval_seconds=1.0,
            usage_delta_microseconds=10, utilization_fraction=0.01,
            usage_total_microseconds=20,
        ),
    )
    gpu_evidence = GpuPlacementEvidence(
        "gpu-evidence-1", gpu_request, gpu_decision, gpu_after,
        5_000_000_000, 3_000_000_000, 2_000_000_000, 1.0,
        3_000_000_000.0, 6_000_000_000, 3_000_000_000,
        True, True, "0" * 64,
    )
    gpu_evidences = (
        gpu_evidence,
        _gpu_clone(gpu_evidence, "expert.llama", "llama3.2:3b", 28, 28, 2),
        _gpu_clone(gpu_evidence, "expert.laguna", "laguna-xs.2:q4_K_M", 40, 16, 3),
        _gpu_clone(gpu_evidence, "expert.gemma", "gemma4:26b", 30, 8, 4),
    )
    gpu_report = FullWorkstationGpuReport(
        "gpu-report-1", NOW, NOW + timedelta(seconds=5),
        "full-reference-workstation", observation.budget_id, "fam-gpu",
        gpu_evidences, 10_000_000_000, 100, 10, 5, "inactive", (),
    )
    storage_artifact = ModelStorageArtifact(
        "artifact.model", "model:latest", "a" * 64, 8192, 8192,
        "storage-root", StorageMedium.NVME, "ext4", True, False, True,
    )
    cache_before = _cache("cache-before", 2)
    cold_before = _cache("cold-before", 0)
    cold_after = _cache("cold-after", 2)
    warm_after = _cache("warm-after", 2)
    io_budget = ModelLoadIoBudget(
        "io-budget-1", storage_artifact.artifact_id, 16384, 4096,
        1_000_000, 500_000, False, True,
    )
    cold_trial = ModelLoadIoTrial(
        "cold-trial", LoadCacheState.COLD, cold_before, cold_after,
        8192, 0, 9000, 1.0, 10_000, 20_000, True, True, True,
    )
    warm_trial = ModelLoadIoTrial(
        "warm-trial", LoadCacheState.WARM, cold_after, warm_after,
        0, 0, 9000, 0.5, 10_000, 20_000, False, False, True,
    )
    storage_evidence = StoragePagingEvidence(
        "storage-evidence-1", storage_artifact, io_budget, cache_before,
        cold_trial, warm_trial, "inactive", (),
    )
    npu_report = NpuInvestigationReport(
        "npu-report-1", NOW, NOW + timedelta(seconds=1),
        "full-reference-workstation", NpuInvestigationOutcome.SUPPORTED,
        NpuHardwareEvidence(
            "0x8086", "0xad1d", "Intel Arrow Lake NPU", "intel_vpu", "1.0.0",
            "ubuntu 24.04", "6.17.0", True, False, True,
            "docker-device-pass-through-with-device-group",
        ),
        NpuRuntimeEvidence(
            "OpenVINO", "2026.2.0", "1.33.0", "1.27.0", ("CPU", "NPU"),
            "Intel(R) AI Boost", "NPU", ("NPU",), False, True,
        ),
        NpuMicroExpertEvidence(
            "expert.route.npu", "route.intent.linear.v1", "openvino-ir",
            "a" * 64, "b" * 64, "c" * 64, "code", "code",
            ("code", "retrieval", "math", "general"), (0.97, 0.01, 0.01, 0.01),
            10.0, 2.0, (1.0, 1.0, 1.0), False,
        ),
        None,
    )
    cache_snapshot = CacheTelemetrySnapshot(
        "cache-snapshot-1", 1, None, NOW,
        (CacheTelemetryEntry(
            "artifact.model", CacheTier.HOST_PAGE_CACHE, CacheEntryState.WARM,
            8192, 8192, 2, 1, NOW, 5.0, True, "d" * 64,
        ),), True,
    )
    cache_request = CachePolicyRequest(
        "cache-request-1", cache_snapshot,
        (CacheTierPressure(CacheTier.HOST_PAGE_CACHE, 4096),), (),
    )
    cache_decision = DeterministicCacheRetentionPolicy().decide(
        "cache-decision-1", cache_request
    )
    replay_records = tuple(SchedulerPolicyReplayRecord(
        f"replay-{index}", kind, CACHE_POLICY_VERSION,
        "fam.input/v1alpha1", "fam.output/v1alpha1",
        str(index) * 64, str(index + 3) * 64, str(index + 3) * 64,
        True, False,
    ) for index, kind in enumerate(SchedulerPolicyKind, start=1))
    replay_report = SchedulerPolicyReplayReport(
        "replay-report-1", NOW, replay_records, True,
    )
    prefetch_values = _prefetch_values(cache_snapshot)
    frequency = LocalExpertFrequencyLearner().learn("frequency-1", (
        ExpertUseObservation("use-1", "expert.small", NOW, True),
        ExpertUseObservation("use-2", "expert.small", NOW, True),
    ))
    baseline_first = replace(
        observation,
        validation_profile_id="compat-cpu-16gb",
        accelerators=tuple(
            replace(
                item, placement_allowed=False, scheduler_limit_bytes=0,
                current_bytes=0, available_for_new_bytes=0,
            )
            for item in observation.accelerators
        ),
    )
    completed = replace(
        baseline_first,
        observation_id="live-2",
        sequence=2,
        previous_observation_id=baseline_first.observation_id,
        observed_at=NOW + timedelta(seconds=1),
        status=ObservationStatus.COMPLETE,
        cpu=replace(
            baseline_first.cpu,
            interval_seconds=1.0,
            usage_delta_microseconds=10,
            utilization_fraction=0.01,
            usage_total_microseconds=20,
        ),
    )
    attempts = (
        _baseline_attempt("expert.llama", "llama3.2:3b", True, 1),
        _baseline_attempt("expert.qwen", "qwen2.5-coder:7b", True, 2),
        _baseline_attempt("expert.laguna", "laguna-xs.2:q4_K_M", False, 3),
        _baseline_attempt("expert.gemma", "gemma4:26b", False, 4),
    )
    baseline = CpuOnlyBaselineReport(
        "cpu-baseline-1", NOW, NOW + timedelta(seconds=2), "compat-cpu-16gb",
        observation.budget_id, "fam-cpu-baseline", 16 * 1024**3,
        14 * 1024**3, 2 * 1024**3, 8 * 1024**3, 0, 0, 4.0, 100,
        CPU_ONLY_ENVIRONMENT, (baseline_first, completed), attempts,
        ("llama3.2:3b", "qwen2.5-coder:7b"), 0,
        "inactive", (),
    )
    return (
        observation, profile, reservation, estimate, residency, admission, decision,
        baseline, gpu_request, gpu_decision, gpu_evidence, gpu_report,
        storage_artifact, cold_before, storage_evidence,
        npu_report,
        cache_snapshot, cache_request, cache_decision, replay_report,
        *prefetch_values,
        frequency,
    )


def _cache(identifier, resident_pages):
    return ArtifactCacheObservation(
        identifier, "artifact.model", NOW, 8192, 4096, 2, resident_pages,
        resident_pages * 4096, resident_pages / 2, True,
    )


def _gpu_clone(base, expert_id, model_ref, total_layers, layers, suffix):
    request = GpuPlacementRequest(
        f"gpu-request-{suffix}", expert_id, base.request.observation,
        ResidentWeightEstimate(
            expert_id, model_ref, 5_000_000_000,
            WeightEstimateSource.DECLARED_CONSERVATIVE, "fixture weight bound",
        ),
        base.request.context, "gpu-0", total_layers, layers, 0,
    )
    decision = DeterministicGpuPlacementPolicy().decide(
        f"gpu-decision-{suffix}", request
    )
    after = replace(
        base.after_load_observation,
        observation_id=f"gpu-live-{suffix}",
        previous_observation_id=request.observation.observation_id,
    )
    accelerator = min(3_000_000_000, decision.accelerator_reservation_bytes)
    return GpuPlacementEvidence(
        f"gpu-evidence-{suffix}", request, decision, after,
        5_000_000_000, accelerator, 5_000_000_000 - accelerator,
        1.0, float(accelerator), 6_000_000_000, accelerator,
        True, True, str(suffix) * 64,
    )


def _baseline_attempt(expert_id, model_ref, admitted, suffix):
    status = AdmissionStatus.ADMITTED if admitted else AdmissionStatus.REJECTED
    decision = AdmissionDecision(
        f"baseline-decision-{suffix}", f"baseline-request-{suffix}", status,
        1_000, 100, 1_100, 2_000, 0, (), 0,
        900 if admitted else 0,
        (("memory.admitted_without_eviction" if admitted else "memory.insufficient_after_safe_eviction"), "placement.host_memory_only"),
    )
    return CpuBaselineExpertAttempt(
        expert_id, model_ref, decision, admitted,
        "0" * 64 if admitted else None,
        1_000 if admitted else None,
        0 if admitted else None,
    )


def _prefetch_values(snapshot):
    sequence = ArtifactAccessSequence(
        "history-1", NOW, ("artifact.current", "artifact.model"), "e" * 64,
    )
    candidate = PrefetchCandidate(
        "artifact.model", CacheTier.HOST_PAGE_CACHE, 8192, 4096, 5.0,
    )
    prediction_request = PrefetchPredictionRequest(
        "prediction-request-1", "artifact.current", NOW, (candidate,),
        (sequence, replace(sequence, sequence_id="history-2")), 2, 1.0, 60,
    )
    prediction = DeterministicTransitionPredictor().predict("prediction-1", prediction_request)
    cold_snapshot = replace(
        snapshot, snapshot_id="prefetch-snapshot", entries=(replace(
            snapshot.entries[0], state=CacheEntryState.COLD, observed_bytes=0,
            hit_count=0, last_accessed_at=None, evictable=False,
        ),),
    )
    budget = PrefetchResourceBudget(4096, 4096, 8192, 16384, 4096, 1, 8192, 0)
    policy_request = PrefetchPolicyRequest(
        "prefetch-request-1", prediction, cold_snapshot, budget, NOW, 0, False,
    )
    policy = DeterministicPrefetchAdmissionPolicy()
    decision = policy.decide("prefetch-decision-1", policy_request)
    execution = PrefetchExecutionEvidence(
        "execution-1", prediction, decision, NOW, NOW + timedelta(seconds=1),
        4096, 4096, 4096, 4096, 0, 0, 4096, "f" * 64, "f" * 64, True, True,
    )
    guard_request = replace(
        policy_request, request_id="guard-request-1",
        budget=replace(budget, current_waste_bytes=8192),
    )
    guard = policy.decide("guard-decision-1", guard_request)
    report = PredictivePrefetchReport(
        "prefetch-report-1", prediction_request, prediction, policy_request,
        decision, execution, guard_request, guard,
    )
    return prediction_request, prediction, policy_request, decision, report
