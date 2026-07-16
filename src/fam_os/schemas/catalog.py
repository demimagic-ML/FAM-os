"""Catalog of public Phase 2 serialized document roots."""

from __future__ import annotations

from fam_os.applications import (
    APPLICATION_ACTION_AUDIT_VERSION,
    APPLICATION_CONTRACT_VERSION,
    APPLICATION_FAILURE_CONTRACT_VERSION,
    ActionConfirmation,
    ActionPreparationRequest,
    ActionProposal,
    ActionResult,
    ApplicationActionAuditIntent,
    ApplicationActionAuditRecord,
    ApplicationFailure,
    ApplicationIdentity,
    ApplicationInstance,
    CapabilityDescriptor,
    CapabilityRegistryEntry,
    ConnectorEvent,
    ConnectorRegistration,
    ObservationRequest,
    ObservationResult,
    PermissionGrant,
)
from fam_os.applications.manifest import CONNECTOR_MANIFEST_CONTRACT_VERSION, ConnectorManifest
from fam_os.core.contracts import (
    CORE_CONTRACT_VERSION,
    FAILURE_CONTRACT_VERSION,
    DegradationNotice,
    ExecutionPlan,
    FailureEnvelope,
    TaskRequest,
    TaskResult,
)
from fam_os.experts import (
    EXPERT_BENCHMARK_METADATA_VERSION,
    EXPERT_COMPATIBILITY_CONTRACT_VERSION,
    EXPERT_MANIFEST_CONTRACT_VERSION,
    EXPERT_ROUTING_METADATA_VERSION,
    EXPERT_RUNTIME_BINDING_VERSION,
    LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION,
    ExpertBenchmarkRun,
    ExpertCompatibilityReport,
    ExpertManifest,
    ExpertManifestV1Alpha1,
    ExpertRoutingEmbedding,
    ExpertRuntimeBinding,
    MIXED_BENCHMARK_CONTRACT_VERSION,
    MixedBenchmarkReport,
    MixedBenchmarkSuite,
    MICRO_EXPERT_CONTRACT_VERSION,
    MicroExpertAdvice,
    MicroExpertBenchmarkReport,
    ESCALATION_TRACE_CONTRACT_VERSION,
    EscalationTraceReport,
    RETRIEVAL_EVIDENCE_CONTRACT_VERSION,
    RETRIEVAL_TIERS_CONTRACT_VERSION,
    RetrievalTierEvidence,
    VerifiedRetrievalResult,
    MATH_EVIDENCE_CONTRACT_VERSION,
    MATH_EXPERT_CONTRACT_VERSION,
    MathExpertEvidence,
    MathReasoningAdvice,
    MathSolverRequest,
    MathSolverResult,
    MEDIA_EVIDENCE_CONTRACT_VERSION,
    MediaExpertEvidence,
    EFFICIENCY_REPORT_CONTRACT_VERSION,
    ExpertEfficiencyReport,
    EXPERT_EVOLUTION_CONTRACT_VERSION,
    ExpertEvolutionProposal,
    ExpertEvolutionReport,
    ExpertPerformanceSlice,
    PHASE9_EXIT_CONTRACT_VERSION,
    Phase9ExitEvidence,
)
from fam_os.memory import (
    MEMORY_LIFECYCLE_CONTRACT_VERSION,
    MEMORY_RECORD_MANIFEST_CONTRACT_VERSION,
    MemoryDeletionReceipt,
    MemoryDeletionRequest,
    MemoryExpiryEvaluation,
    MemoryRecordManifest,
    MEMORY_ACCESS_CONTRACT_VERSION,
    MemoryAccessContext,
    DOCUMENT_INDEX_CONTRACT_VERSION,
    DocumentIndexApproval,
    DocumentIndexEvidence,
    DocumentRetrievalHit,
    IndexedDocumentChunk,
    MEMORY_RELEVANCE_CONTRACT_VERSION,
    MemoryRelevanceDecision,
    MemoryRetrievalCandidate,
    MEMORY_MANAGEMENT_CONTRACT_VERSION,
    MemoryDocumentExport,
    MemoryManagementEvidence,
    MEMORY_ENCRYPTION_CONTRACT_VERSION,
    MemoryEncryptionEvidence,
    MEMORY_QUALITY_CONTRACT_VERSION,
    MemoryQualityPrivacyReport,
    PHASE10_EXIT_CONTRACT_VERSION,
    Phase10ExitEvidence,
)
from fam_os.adaptation import (
    OUTCOME_PREDICTION_CONTRACT_VERSION,
    VerifiedOutcomeObservation,
    WorkflowOutcomePrediction,
    PREFERENCE_CONTRACT_VERSION,
    PreferenceResetReceipt,
    UserPreferenceProfile,
    RESOURCE_ADAPTATION_CONTRACT_VERSION,
    OperatingPolicyDecision,
    OperatingState,
    ADAPTATION_DRIFT_CONTRACT_VERSION,
    AdaptationDriftReport,
    AdaptationRollbackReceipt,
    AdaptationSnapshot,
    PHASE11_EXIT_CONTRACT_VERSION,
    Phase11ExitEvidence,
)
from fam_os.fabric import (
    DEVICE_IDENTITY_CONTRACT_VERSION,
    DeviceEnrollmentChallenge,
    DeviceEnrollmentRecord,
    DeviceEnrollmentRequest,
    DeviceIdentity,
    REMOTE_PRIVACY_CONTRACT_VERSION,
    RemoteContextRequest,
    RemoteExpertCapability,
    RemotePrivacyDecision,
    RemotePrivacyPolicy,
    FABRIC_TRANSPORT_CONTRACT_VERSION,
    FabricEncryptedEnvelope,
    FabricHandshake,
    FABRIC_SCHEDULING_CONTRACT_VERSION,
    FabricRouteCandidate,
    FabricRouteDecision,
    FABRIC_RECOVERY_CONTRACT_VERSION,
    FabricRecoveryDecision,
    FABRIC_DEMO_CONTRACT_VERSION,
    MultiDeviceDemoReport,
)
from fam_os.expert_factory import (
    EXPERT_DISCOVERY_CONTRACT_VERSION, FACTORY_LIFECYCLE_CONTRACT_VERSION,
    FACTORY_OBJECTIVE_CONTRACT_VERSION, FACTORY_PIPELINE_CONTRACT_VERSION,
    FACTORY_QUANTIZATION_CONTRACT_VERSION, FACTORY_REGRESSION_CONTRACT_VERSION,
    FACTORY_RELEASE_CONTRACT_VERSION, FACTORY_TRAINING_CONTRACT_VERSION,
    AdapterTrainingPlan, DistillationPlan, EvaluationPlan, FactoryLifecycleReport,
    FailureTrace, FailureTraceCluster, HardwareTrainingMetrics,
    MissingCapabilityProposal, PublishedExpertPackage, QuantizedVariant,
    RegressionGateResult, TeacherDataset, TrainedMicroExpert,
)
from fam_os.console.contracts import CONSOLE_CONTRACT_VERSION, ConsoleSnapshot
from fam_os.product.benchmark_publication import (
    BENCHMARK_PUBLICATION_VERSION, BenchmarkPublication,
)
from fam_os.product.linux_installation import (
    INSTALL_CONTRACT_VERSION, InstallationReceipt,
)
from fam_os.product.phase14_exit import PHASE14_EXIT_VERSION, Phase14ExitEvidence
from fam_os.product.phase15_exit import PHASE15_EXIT_VERSION, Phase15ExitEvidence
from fam_os.product.recovery_mode import RECOVERY_CONTRACT_VERSION, RecoveryDecision
from fam_os.product.soak_contracts import SOAK_CONTRACT_VERSION, SoakReport
from fam_os.product.update_contracts import UPDATE_CONTRACT_VERSION, UpdateReceipt
from fam_os.security.review import SecurityReviewReport
from fam_os.registry import (
    REGISTRY_TRUST_CONTRACT_VERSION,
    PackageSignature,
    PackageTrustPolicy,
    PackageValidationReport,
)
from fam_os.registry.lifecycle_contracts import (
    PACKAGE_LIFECYCLE_CONTRACT_VERSION,
    ExpertPackageInstallationState,
)
from fam_os.routing import ROUTING_CONTRACT_VERSION, RoutingRequest, RoutingResult
from fam_os.core.lifecycle.global_budget import (
    GLOBAL_ATTEMPT_BUDGET_VERSION,
    AttemptBudgetReservation,
    GlobalAttemptBudget,
    GlobalAttemptBudgetSnapshot,
)
from fam_os.scheduler.resources import (
    EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION,
    HOST_INVENTORY_CONTRACT_VERSION,
    EffectiveResourceBudget,
    HostInventory,
)
from fam_os.scheduler.frequency_learning import (
    EXPERT_FREQUENCY_CONTRACT_VERSION,
    ExpertFrequencyProfile,
)
from fam_os.scheduler.live_contracts import (
    LIVE_RESOURCE_OBSERVATION_VERSION,
    SchedulerResourceObservation,
)
from fam_os.scheduler.context_contracts import (
    CONTEXT_MEMORY_CONTRACT_VERSION,
    ContextMemoryEstimate,
    ContextMemoryModelProfile,
    ContextMemoryReservation,
)
from fam_os.scheduler.residency_contracts import (
    EXPERT_RESIDENCY_CONTRACT_VERSION,
    ExpertResidencyCatalog,
)
from fam_os.scheduler.admission_contracts import (
    ADMISSION_CONTRACT_VERSION,
    AdmissionDecision,
    AdmissionRequest,
)
from fam_os.scheduler.baseline_contracts import (
    CPU_BASELINE_CONTRACT_VERSION,
    CpuOnlyBaselineReport,
)
from fam_os.scheduler.gpu_contracts import (
    GPU_PLACEMENT_CONTRACT_VERSION,
    GpuPlacementDecision,
    GpuPlacementEvidence,
    GpuPlacementRequest,
    FullWorkstationGpuReport,
)
from fam_os.scheduler.storage_contracts import (
    STORAGE_PAGING_CONTRACT_VERSION,
    ArtifactCacheObservation,
    ModelStorageArtifact,
    StoragePagingEvidence,
)
from fam_os.scheduler.npu_contracts import (
    NPU_INVESTIGATION_CONTRACT_VERSION,
    NpuInvestigationReport,
)
from fam_os.scheduler.cache_contracts import (
    CACHE_POLICY_CONTRACT_VERSION,
    CachePolicyDecision,
    CachePolicyRequest,
    CacheTelemetrySnapshot,
)
from fam_os.scheduler.replay_contracts import (
    POLICY_REPLAY_CONTRACT_VERSION,
    SchedulerPolicyReplayReport,
)
from fam_os.scheduler.prefetch_prediction import (
    PREFETCH_CONTRACT_VERSION,
    PrefetchPrediction,
    PrefetchPredictionRequest,
)
from fam_os.scheduler.prefetch_contracts import (
    PredictivePrefetchReport,
    PrefetchPolicyDecision,
    PrefetchPolicyRequest,
)
from fam_os.scheduler.configuration import (
    CONFIGURATION_CONTRACT_VERSION,
    ComposedResourceConfiguration,
    ConfigurationCompositionRequest,
    DiscoveredResourceState,
    SchedulerDefaults,
    SessionResourceOverride,
    UserResourcePolicy,
    ValidationProfileConfiguration,
    VALIDATION_PROFILE_DOCUMENT_CONTRACT_VERSION,
    ValidationProfileDocument,
)
from fam_os.shell import (
    SHELL_CONTRACT_VERSION,
    ShellAskCommand,
    ShellCancelCommand,
    ShellDecisionCommand,
    ShellSessionSnapshot,
    ShellSnapshotQuery,
)
from fam_os.schemas.descriptor import SchemaDescriptor
from fam_os.verification import (
    VERIFIER_ACTIVATION_DECISION_VERSION,
    VERIFIER_MANIFEST_CONTRACT_VERSION,
    VERIFIER_RUNTIME_BINDING_VERSION,
    VERIFIER_TRUST_POLICY_VERSION,
    VerifierActivationDecision,
    VerifierManifest,
    VerifierRuntimeBinding,
    VerifierTrustPolicy,
)
from fam_os.verification.python.quality import (
    PYTHON_QUALITY_CONTRACT_VERSION,
    PythonQualityReport,
)
from fam_os.verification.language_quality import (
    LANGUAGE_QUALITY_CONTRACT_VERSION,
    LanguageQualityReport,
)
from fam_os.verification.math_contracts import (
    MATH_VERIFICATION_CONTRACT_VERSION,
    MathVerificationReport,
    MathVerificationRequest,
)
from fam_os.verification.retrieval import (
    RETRIEVAL_VERIFICATION_CONTRACT_VERSION,
    RetrievalVerificationReport,
)


def _entry(
    family: str,
    version: str,
    root: type[object],
    title: str,
    schema_version: str = "v1alpha1",
) -> SchemaDescriptor:
    return SchemaDescriptor(f"{family}/{schema_version}", version, root, title)


SCHEMA_DESCRIPTORS = (
    _entry("fam.core.task-request", CORE_CONTRACT_VERSION, TaskRequest, "FAM task request"),
    _entry("fam.core.execution-plan", CORE_CONTRACT_VERSION, ExecutionPlan, "FAM execution plan"),
    _entry("fam.core.task-result", CORE_CONTRACT_VERSION, TaskResult, "FAM task result"),
    _entry("fam.routing.request", ROUTING_CONTRACT_VERSION, RoutingRequest, "Routing request"),
    _entry("fam.routing.result", ROUTING_CONTRACT_VERSION, RoutingResult, "Routing result"),
    _entry("fam.application.identity", APPLICATION_CONTRACT_VERSION, ApplicationIdentity, "Application identity"),
    _entry("fam.application.instance", APPLICATION_CONTRACT_VERSION, ApplicationInstance, "Application instance"),
    _entry("fam.application.capability", APPLICATION_CONTRACT_VERSION, CapabilityDescriptor, "Application capability"),
    _entry("fam.application.registry-entry", APPLICATION_CONTRACT_VERSION, CapabilityRegistryEntry, "Capability registry entry"),
    _entry("fam.application.permission-grant", APPLICATION_CONTRACT_VERSION, PermissionGrant, "Application permission grant"),
    _entry("fam.application.observation-request", APPLICATION_CONTRACT_VERSION, ObservationRequest, "Application observation request"),
    _entry("fam.application.observation-result", APPLICATION_CONTRACT_VERSION, ObservationResult, "Application observation result"),
    _entry("fam.application.action-preparation", APPLICATION_CONTRACT_VERSION, ActionPreparationRequest, "Application action preparation"),
    _entry("fam.application.action-proposal", APPLICATION_CONTRACT_VERSION, ActionProposal, "Application action proposal"),
    _entry("fam.application.action-confirmation", APPLICATION_CONTRACT_VERSION, ActionConfirmation, "Application action confirmation"),
    _entry("fam.application.action-result", APPLICATION_CONTRACT_VERSION, ActionResult, "Application action result"),
    _entry("fam.application.action-audit-intent", APPLICATION_ACTION_AUDIT_VERSION, ApplicationActionAuditIntent, "Application action audit intent"),
    _entry("fam.application.action-audit-record", APPLICATION_ACTION_AUDIT_VERSION, ApplicationActionAuditRecord, "Application action audit record"),
    _entry("fam.application.connector-registration", APPLICATION_CONTRACT_VERSION, ConnectorRegistration, "Application connector registration"),
    _entry("fam.application.connector-event", APPLICATION_CONTRACT_VERSION, ConnectorEvent, "Application connector event"),
    _entry("fam.application.failure", APPLICATION_FAILURE_CONTRACT_VERSION, ApplicationFailure, "Application failure"),
    _entry("fam.hardware.host-inventory", HOST_INVENTORY_CONTRACT_VERSION, HostInventory, "Host inventory"),
    _entry("fam.hardware.effective-budget", EFFECTIVE_RESOURCE_BUDGET_CONTRACT_VERSION, EffectiveResourceBudget, "Effective resource budget"),
    _entry("fam.scheduler.live-resources", LIVE_RESOURCE_OBSERVATION_VERSION, SchedulerResourceObservation, "Live scheduler resource observation"),
    _entry("fam.scheduler.context-profile", CONTEXT_MEMORY_CONTRACT_VERSION, ContextMemoryModelProfile, "Context memory model profile"),
    _entry("fam.scheduler.context-reservation", CONTEXT_MEMORY_CONTRACT_VERSION, ContextMemoryReservation, "Context memory reservation"),
    _entry("fam.scheduler.context-estimate", CONTEXT_MEMORY_CONTRACT_VERSION, ContextMemoryEstimate, "Context memory estimate"),
    _entry("fam.scheduler.expert-residency", EXPERT_RESIDENCY_CONTRACT_VERSION, ExpertResidencyCatalog, "Expert residency catalog"),
    _entry("fam.scheduler.admission-request", ADMISSION_CONTRACT_VERSION, AdmissionRequest, "Scheduler admission request"),
    _entry("fam.scheduler.admission-decision", ADMISSION_CONTRACT_VERSION, AdmissionDecision, "Scheduler admission decision"),
    _entry("fam.scheduler.cpu-baseline", CPU_BASELINE_CONTRACT_VERSION, CpuOnlyBaselineReport, "Constrained CPU-only scheduler baseline"),
    _entry("fam.scheduler.gpu-placement-request", GPU_PLACEMENT_CONTRACT_VERSION, GpuPlacementRequest, "GPU split placement request"),
    _entry("fam.scheduler.gpu-placement-decision", GPU_PLACEMENT_CONTRACT_VERSION, GpuPlacementDecision, "GPU split placement decision"),
    _entry("fam.scheduler.gpu-placement-evidence", GPU_PLACEMENT_CONTRACT_VERSION, GpuPlacementEvidence, "Observed GPU split placement evidence"),
    _entry("fam.scheduler.gpu-placement-report", GPU_PLACEMENT_CONTRACT_VERSION, FullWorkstationGpuReport, "Full workstation GPU placement report"),
    _entry("fam.scheduler.storage-artifact", STORAGE_PAGING_CONTRACT_VERSION, ModelStorageArtifact, "SSD model storage artifact"),
    _entry("fam.scheduler.artifact-cache", STORAGE_PAGING_CONTRACT_VERSION, ArtifactCacheObservation, "Mmap artifact cache observation"),
    _entry("fam.scheduler.storage-paging-evidence", STORAGE_PAGING_CONTRACT_VERSION, StoragePagingEvidence, "SSD paging and load I/O evidence"),
    _entry("fam.scheduler.npu-investigation", NPU_INVESTIGATION_CONTRACT_VERSION, NpuInvestigationReport, "Intel NPU micro-expert investigation"),
    _entry("fam.scheduler.cache-telemetry", CACHE_POLICY_CONTRACT_VERSION, CacheTelemetrySnapshot, "Tier-separated cache telemetry"),
    _entry("fam.scheduler.cache-policy-request", CACHE_POLICY_CONTRACT_VERSION, CachePolicyRequest, "Cache retention policy request"),
    _entry("fam.scheduler.cache-policy-decision", CACHE_POLICY_CONTRACT_VERSION, CachePolicyDecision, "Cache retention policy decision"),
    _entry("fam.scheduler.policy-replay", POLICY_REPLAY_CONTRACT_VERSION, SchedulerPolicyReplayReport, "Offline scheduler policy replay report"),
    _entry("fam.scheduler.prefetch-prediction-request", PREFETCH_CONTRACT_VERSION, PrefetchPredictionRequest, "Bounded prefetch prediction request"),
    _entry("fam.scheduler.prefetch-prediction", PREFETCH_CONTRACT_VERSION, PrefetchPrediction, "Historical transition prediction"),
    _entry("fam.scheduler.prefetch-policy-request", PREFETCH_CONTRACT_VERSION, PrefetchPolicyRequest, "Predictive prefetch admission request"),
    _entry("fam.scheduler.prefetch-policy-decision", PREFETCH_CONTRACT_VERSION, PrefetchPolicyDecision, "Predictive prefetch admission decision"),
    _entry("fam.scheduler.predictive-prefetch-report", PREFETCH_CONTRACT_VERSION, PredictivePrefetchReport, "Bounded predictive prefetch evidence"),
    _entry("fam.scheduler.expert-frequency-profile", EXPERT_FREQUENCY_CONTRACT_VERSION, ExpertFrequencyProfile, "Local expert frequency profile"),
    _entry("fam.configuration.scheduler-defaults", CONFIGURATION_CONTRACT_VERSION, SchedulerDefaults, "Scheduler safe defaults"),
    _entry("fam.configuration.validation-profile", CONFIGURATION_CONTRACT_VERSION, ValidationProfileConfiguration, "Named validation profile configuration"),
    _entry("fam.configuration.user-policy", CONFIGURATION_CONTRACT_VERSION, UserResourcePolicy, "User resource policy"),
    _entry("fam.configuration.session-override", CONFIGURATION_CONTRACT_VERSION, SessionResourceOverride, "Session resource override"),
    _entry("fam.configuration.discovered-state", CONFIGURATION_CONTRACT_VERSION, DiscoveredResourceState, "Discovered resource state"),
    _entry("fam.configuration.composition-request", CONFIGURATION_CONTRACT_VERSION, ConfigurationCompositionRequest, "Configuration composition request"),
    _entry("fam.configuration.composed-resources", CONFIGURATION_CONTRACT_VERSION, ComposedResourceConfiguration, "Composed resource configuration"),
    _entry("fam.configuration.validation-profile-document", VALIDATION_PROFILE_DOCUMENT_CONTRACT_VERSION, ValidationProfileDocument, "Validation profile document"),
    _entry(
        "fam.expert.manifest",
        LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION,
        ExpertManifestV1Alpha1,
        "Legacy expert manifest",
    ),
    _entry(
        "fam.expert.compatibility-report",
        EXPERT_COMPATIBILITY_CONTRACT_VERSION,
        ExpertCompatibilityReport,
        "Expert compatibility report",
    ),
    _entry(
        "fam.expert.routing-embedding",
        EXPERT_ROUTING_METADATA_VERSION,
        ExpertRoutingEmbedding,
        "Expert semantic routing embedding",
    ),
    _entry(
        "fam.expert.benchmark-run",
        EXPERT_BENCHMARK_METADATA_VERSION,
        ExpertBenchmarkRun,
        "Expert benchmark run metadata",
    ),
    _entry(
        "fam.expert.runtime-binding",
        EXPERT_RUNTIME_BINDING_VERSION,
        ExpertRuntimeBinding,
        "Expert runtime artifact binding",
    ),
    _entry("fam.expert.mixed-benchmark-suite", MIXED_BENCHMARK_CONTRACT_VERSION, MixedBenchmarkSuite, "Mixed expert benchmark suite"),
    _entry("fam.expert.mixed-benchmark-report", MIXED_BENCHMARK_CONTRACT_VERSION, MixedBenchmarkReport, "Mixed expert benchmark report"),
    _entry("fam.expert.micro-advice", MICRO_EXPERT_CONTRACT_VERSION, MicroExpertAdvice, "Advisory micro-expert result"),
    _entry("fam.expert.micro-benchmark", MICRO_EXPERT_CONTRACT_VERSION, MicroExpertBenchmarkReport, "Micro-expert benchmark report"),
    _entry("fam.expert.escalation-trace", ESCALATION_TRACE_CONTRACT_VERSION, EscalationTraceReport, "Code escalation trace"),
    _entry("fam.expert.retrieval-result", RETRIEVAL_TIERS_CONTRACT_VERSION, VerifiedRetrievalResult, "Verified three-tier retrieval result"),
    _entry("fam.expert.retrieval-evidence", RETRIEVAL_EVIDENCE_CONTRACT_VERSION, RetrievalTierEvidence, "Three-tier retrieval evidence"),
    _entry("fam.expert.math-reasoning", MATH_EXPERT_CONTRACT_VERSION, MathReasoningAdvice, "Advisory mathematics reasoning"),
    _entry("fam.expert.math-solver-request", MATH_EXPERT_CONTRACT_VERSION, MathSolverRequest, "Deterministic mathematics solver request"),
    _entry("fam.expert.math-solver-result", MATH_EXPERT_CONTRACT_VERSION, MathSolverResult, "Deterministic mathematics solver result"),
    _entry("fam.expert.math-evidence", MATH_EVIDENCE_CONTRACT_VERSION, MathExpertEvidence, "Mathematics expert benchmark evidence"),
    _entry("fam.expert.media-evidence", MEDIA_EVIDENCE_CONTRACT_VERSION, MediaExpertEvidence, "Local media expert evidence"),
    _entry("fam.expert.efficiency-report", EFFICIENCY_REPORT_CONTRACT_VERSION, ExpertEfficiencyReport, "Measured expert efficiency report"),
    _entry("fam.expert.performance-slice", EXPERT_EVOLUTION_CONTRACT_VERSION, ExpertPerformanceSlice, "Expert performance evidence slice"),
    _entry("fam.expert.evolution-proposal", EXPERT_EVOLUTION_CONTRACT_VERSION, ExpertEvolutionProposal, "Advisory expert evolution proposal"),
    _entry("fam.expert.evolution-report", EXPERT_EVOLUTION_CONTRACT_VERSION, ExpertEvolutionReport, "Advisory expert evolution report"),
    _entry("fam.expert.phase9-exit", PHASE9_EXIT_CONTRACT_VERSION, Phase9ExitEvidence, "Phase 9 expert hierarchy exit evidence"),
    _entry(
        "fam.expert.manifest",
        EXPERT_MANIFEST_CONTRACT_VERSION,
        ExpertManifest,
        "Expert manifest",
        "v1alpha2",
    ),
    _entry("fam.verifier.manifest", VERIFIER_MANIFEST_CONTRACT_VERSION, VerifierManifest, "Verifier manifest"),
    _entry("fam.verifier.runtime-binding", VERIFIER_RUNTIME_BINDING_VERSION, VerifierRuntimeBinding, "Verifier runtime binding"),
    _entry("fam.verifier.trust-policy", VERIFIER_TRUST_POLICY_VERSION, VerifierTrustPolicy, "Verifier trust policy"),
    _entry("fam.verifier.activation-decision", VERIFIER_ACTIVATION_DECISION_VERSION, VerifierActivationDecision, "Verifier activation decision"),
    _entry("fam.verifier.python-quality", PYTHON_QUALITY_CONTRACT_VERSION, PythonQualityReport, "Python quality verification report"),
    _entry("fam.verifier.language-quality", LANGUAGE_QUALITY_CONTRACT_VERSION, LanguageQualityReport, "Language quality verification report"),
    _entry("fam.verifier.math-request", MATH_VERIFICATION_CONTRACT_VERSION, MathVerificationRequest, "Math verification request"),
    _entry("fam.verifier.math-report", MATH_VERIFICATION_CONTRACT_VERSION, MathVerificationReport, "Math verification report"),
    _entry("fam.verifier.retrieval-report", RETRIEVAL_VERIFICATION_CONTRACT_VERSION, RetrievalVerificationReport, "Retrieval verification report"),
    _entry("fam.core.global-attempt-budget", GLOBAL_ATTEMPT_BUDGET_VERSION, GlobalAttemptBudget, "Global attempt budget"),
    _entry("fam.core.attempt-budget-reservation", GLOBAL_ATTEMPT_BUDGET_VERSION, AttemptBudgetReservation, "Attempt budget reservation"),
    _entry("fam.core.global-attempt-budget-snapshot", GLOBAL_ATTEMPT_BUDGET_VERSION, GlobalAttemptBudgetSnapshot, "Global attempt budget snapshot"),
    _entry("fam.connector.manifest", CONNECTOR_MANIFEST_CONTRACT_VERSION, ConnectorManifest, "Connector manifest"),
    _entry("fam.memory.record", MEMORY_RECORD_MANIFEST_CONTRACT_VERSION, MemoryRecordManifest, "Memory record manifest"),
    _entry("fam.memory.expiry-evaluation", MEMORY_LIFECYCLE_CONTRACT_VERSION, MemoryExpiryEvaluation, "Memory expiry evaluation"),
    _entry("fam.memory.deletion-request", MEMORY_LIFECYCLE_CONTRACT_VERSION, MemoryDeletionRequest, "Memory deletion request"),
    _entry("fam.memory.deletion-receipt", MEMORY_LIFECYCLE_CONTRACT_VERSION, MemoryDeletionReceipt, "Memory deletion receipt"),
    _entry("fam.memory.access-context", MEMORY_ACCESS_CONTRACT_VERSION, MemoryAccessContext, "Scoped memory access context"),
    _entry("fam.memory.document-approval", DOCUMENT_INDEX_CONTRACT_VERSION, DocumentIndexApproval, "Approved document index grant"),
    _entry("fam.memory.document-chunk", DOCUMENT_INDEX_CONTRACT_VERSION, IndexedDocumentChunk, "Embedded approved document chunk"),
    _entry("fam.memory.document-hit", DOCUMENT_INDEX_CONTRACT_VERSION, DocumentRetrievalHit, "Scoped document retrieval hit"),
    _entry("fam.memory.document-index-evidence", DOCUMENT_INDEX_CONTRACT_VERSION, DocumentIndexEvidence, "Approved document index evidence"),
    _entry("fam.memory.retrieval-candidate", MEMORY_RELEVANCE_CONTRACT_VERSION, MemoryRetrievalCandidate, "Scoped memory retrieval candidate"),
    _entry("fam.memory.relevance-decision", MEMORY_RELEVANCE_CONTRACT_VERSION, MemoryRelevanceDecision, "Memory relevance gate decision"),
    _entry("fam.memory.document-export", MEMORY_MANAGEMENT_CONTRACT_VERSION, MemoryDocumentExport, "Digest-verified memory document export"),
    _entry("fam.memory.management-evidence", MEMORY_MANAGEMENT_CONTRACT_VERSION, MemoryManagementEvidence, "Memory management lifecycle evidence"),
    _entry("fam.memory.encryption-evidence", MEMORY_ENCRYPTION_CONTRACT_VERSION, MemoryEncryptionEvidence, "Owner-isolated memory encryption evidence"),
    _entry("fam.memory.quality-privacy-report", MEMORY_QUALITY_CONTRACT_VERSION, MemoryQualityPrivacyReport, "Memory retrieval quality and privacy report"),
    _entry("fam.memory.phase10-exit", PHASE10_EXIT_CONTRACT_VERSION, Phase10ExitEvidence, "Phase 10 memory-fabric exit evidence"),
    _entry("fam.adaptation.verified-outcome", OUTCOME_PREDICTION_CONTRACT_VERSION, VerifiedOutcomeObservation, "Verified local workflow outcome"),
    _entry("fam.adaptation.workflow-prediction", OUTCOME_PREDICTION_CONTRACT_VERSION, WorkflowOutcomePrediction, "Local context and escalation prediction"),
    _entry("fam.adaptation.preference-profile", PREFERENCE_CONTRACT_VERSION, UserPreferenceProfile, "Inspectable user preference profile"),
    _entry("fam.adaptation.preference-reset", PREFERENCE_CONTRACT_VERSION, PreferenceResetReceipt, "User preference reset receipt"),
    _entry("fam.adaptation.operating-state", RESOURCE_ADAPTATION_CONTRACT_VERSION, OperatingState, "Observed battery thermal load and idle state"),
    _entry("fam.adaptation.operating-policy", RESOURCE_ADAPTATION_CONTRACT_VERSION, OperatingPolicyDecision, "Operating-state adaptation policy"),
    _entry("fam.adaptation.snapshot", ADAPTATION_DRIFT_CONTRACT_VERSION, AdaptationSnapshot, "Immutable adaptation snapshot"),
    _entry("fam.adaptation.drift-report", ADAPTATION_DRIFT_CONTRACT_VERSION, AdaptationDriftReport, "Adaptation drift report"),
    _entry("fam.adaptation.rollback-receipt", ADAPTATION_DRIFT_CONTRACT_VERSION, AdaptationRollbackReceipt, "Adaptation rollback receipt"),
    _entry("fam.adaptation.phase11-exit", PHASE11_EXIT_CONTRACT_VERSION, Phase11ExitEvidence, "Phase 11 repeated-workflow exit evidence"),
    _entry("fam.fabric.device-identity", DEVICE_IDENTITY_CONTRACT_VERSION, DeviceIdentity, "Cryptographic device identity"),
    _entry("fam.fabric.enrollment-request", DEVICE_IDENTITY_CONTRACT_VERSION, DeviceEnrollmentRequest, "Device enrollment request"),
    _entry("fam.fabric.enrollment-challenge", DEVICE_IDENTITY_CONTRACT_VERSION, DeviceEnrollmentChallenge, "Device proof-of-key challenge"),
    _entry("fam.fabric.enrollment-record", DEVICE_IDENTITY_CONTRACT_VERSION, DeviceEnrollmentRecord, "Owner-bound trusted device enrollment"),
    _entry("fam.fabric.remote-capability", REMOTE_PRIVACY_CONTRACT_VERSION, RemoteExpertCapability, "Remote expert capability"),
    _entry("fam.fabric.remote-privacy-policy", REMOTE_PRIVACY_CONTRACT_VERSION, RemotePrivacyPolicy, "Remote context privacy policy"),
    _entry("fam.fabric.remote-context-request", REMOTE_PRIVACY_CONTRACT_VERSION, RemoteContextRequest, "Remote context request"),
    _entry("fam.fabric.remote-privacy-decision", REMOTE_PRIVACY_CONTRACT_VERSION, RemotePrivacyDecision, "Remote privacy decision"),
    _entry("fam.fabric.handshake", FABRIC_TRANSPORT_CONTRACT_VERSION, FabricHandshake, "Signed fabric handshake"),
    _entry("fam.fabric.encrypted-envelope", FABRIC_TRANSPORT_CONTRACT_VERSION, FabricEncryptedEnvelope, "Authenticated encrypted fabric envelope"),
    _entry("fam.fabric.route-candidate", FABRIC_SCHEDULING_CONTRACT_VERSION, FabricRouteCandidate, "Local or remote fabric route candidate"),
    _entry("fam.fabric.route-decision", FABRIC_SCHEDULING_CONTRACT_VERSION, FabricRouteDecision, "Latency-aware fabric route decision"),
    _entry("fam.fabric.recovery-decision", FABRIC_RECOVERY_CONTRACT_VERSION, FabricRecoveryDecision, "Remote failure recovery decision"),
    _entry("fam.fabric.multidevice-demo", FABRIC_DEMO_CONTRACT_VERSION, MultiDeviceDemoReport, "Trusted three-device fabric demonstration"),
    _entry("fam.factory.failure-trace", EXPERT_DISCOVERY_CONTRACT_VERSION, FailureTrace, "Verified expert failure trace"),
    _entry("fam.factory.failure-cluster", EXPERT_DISCOVERY_CONTRACT_VERSION, FailureTraceCluster, "Clustered expert failures"),
    _entry("fam.factory.missing-capability", EXPERT_DISCOVERY_CONTRACT_VERSION, MissingCapabilityProposal, "Missing capability proposal"),
    _entry("fam.factory.teacher-dataset", FACTORY_PIPELINE_CONTRACT_VERSION, TeacherDataset, "Teacher dataset"),
    _entry("fam.factory.distillation-plan", FACTORY_PIPELINE_CONTRACT_VERSION, DistillationPlan, "Distillation plan"),
    _entry("fam.factory.adapter-plan", FACTORY_PIPELINE_CONTRACT_VERSION, AdapterTrainingPlan, "Adapter training plan"),
    _entry("fam.factory.evaluation-plan", FACTORY_PIPELINE_CONTRACT_VERSION, EvaluationPlan, "Expert evaluation plan"),
    _entry("fam.factory.trained-micro-expert", FACTORY_TRAINING_CONTRACT_VERSION, TrainedMicroExpert, "Trained local micro-expert"),
    _entry("fam.factory.hardware-metrics", FACTORY_OBJECTIVE_CONTRACT_VERSION, HardwareTrainingMetrics, "Hardware-aware training metrics"),
    _entry("fam.factory.quantized-variant", FACTORY_QUANTIZATION_CONTRACT_VERSION, QuantizedVariant, "Calibrated quantized expert variant"),
    _entry("fam.factory.published-package", FACTORY_RELEASE_CONTRACT_VERSION, PublishedExpertPackage, "Signed published expert package"),
    _entry("fam.factory.regression-gate", FACTORY_REGRESSION_CONTRACT_VERSION, RegressionGateResult, "Continuous expert regression gate"),
    _entry("fam.factory.lifecycle-report", FACTORY_LIFECYCLE_CONTRACT_VERSION, FactoryLifecycleReport, "End-to-end Expert Factory lifecycle"),
    _entry("fam.product.security-review", "fam.product.security-review/v1alpha1", SecurityReviewReport, "Release security review"),
    _entry("fam.product.update-receipt", UPDATE_CONTRACT_VERSION, UpdateReceipt, "Atomic release update receipt"),
    _entry("fam.product.recovery-decision", RECOVERY_CONTRACT_VERSION, RecoveryDecision, "Recovery-mode decision"),
    _entry("fam.product.soak-report", SOAK_CONTRACT_VERSION, SoakReport, "Production soak report"),
    _entry("fam.product.installation-receipt", INSTALL_CONTRACT_VERSION, InstallationReceipt, "Linux installation receipt"),
    _entry("fam.console.snapshot", CONSOLE_CONTRACT_VERSION, ConsoleSnapshot, "FAM Console snapshot"),
    _entry("fam.product.benchmark-publication", BENCHMARK_PUBLICATION_VERSION, BenchmarkPublication, "Reference benchmark publication"),
    _entry("fam.product.phase14-exit", PHASE14_EXIT_VERSION, Phase14ExitEvidence, "Phase 14 product exit evidence"),
    _entry("fam.product.phase15-exit", PHASE15_EXIT_VERSION, Phase15ExitEvidence, "Installed operational exit evidence"),
    _entry("fam.registry.package-signature", REGISTRY_TRUST_CONTRACT_VERSION, PackageSignature, "Detached package signature"),
    _entry("fam.registry.trust-policy", REGISTRY_TRUST_CONTRACT_VERSION, PackageTrustPolicy, "Package trust policy"),
    _entry("fam.registry.validation-report", REGISTRY_TRUST_CONTRACT_VERSION, PackageValidationReport, "Package validation report"),
    _entry("fam.registry.installation-state", PACKAGE_LIFECYCLE_CONTRACT_VERSION, ExpertPackageInstallationState, "Expert package installation state"),
    _entry("fam.failure.envelope", FAILURE_CONTRACT_VERSION, FailureEnvelope, "FAM failure envelope"),
    _entry("fam.failure.degradation", FAILURE_CONTRACT_VERSION, DegradationNotice, "FAM degradation notice"),
    _entry("fam.shell.ask", SHELL_CONTRACT_VERSION, ShellAskCommand, "FAM Shell ask command"),
    _entry("fam.shell.snapshot-query", SHELL_CONTRACT_VERSION, ShellSnapshotQuery, "FAM Shell snapshot query"),
    _entry("fam.shell.decision", SHELL_CONTRACT_VERSION, ShellDecisionCommand, "FAM Shell decision command"),
    _entry("fam.shell.cancel", SHELL_CONTRACT_VERSION, ShellCancelCommand, "FAM Shell cancellation command"),
    _entry("fam.shell.snapshot", SHELL_CONTRACT_VERSION, ShellSessionSnapshot, "FAM Shell session snapshot"),
)

_BY_SCHEMA_ID = {entry.schema_id: entry for entry in SCHEMA_DESCRIPTORS}
_BY_ROOT_TYPE = {entry.root_type: entry for entry in SCHEMA_DESCRIPTORS}
_KNOWN_FAMILIES = {entry.family_id for entry in SCHEMA_DESCRIPTORS}


def descriptor_for_schema(schema_id: str) -> SchemaDescriptor | None:
    return _BY_SCHEMA_ID.get(schema_id)


def descriptor_for_type(root_type: type[object]) -> SchemaDescriptor | None:
    return _BY_ROOT_TYPE.get(root_type)


def family_is_known(family_id: str) -> bool:
    return family_id in _KNOWN_FAMILIES
    EXPERT_ROUTING_METADATA_VERSION,
    ExpertBenchmarkRun,
    ExpertRoutingEmbedding,
