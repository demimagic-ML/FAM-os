"""Representative hardware and component manifest schema values."""

from dataclasses import replace
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.applications import ApplicationAuthority, ConnectorManifest
from fam_os.experts import (
    BenchmarkAttemptKind,
    BenchmarkOutcome,
    ExpertCompatibilityEvaluator,
    ExpertBenchmarkAttempt,
    ExpertBenchmarkResources,
    ExpertBenchmarkRun,
    ExpertManifest,
    ExpertManifestV1Alpha1,
    ExpertResourceRequirements,
    ExpertRoutingEmbedding,
    ExpertRuntimeBinding,
    ExpertTier,
    VerifierContextDisclosure,
    BenchmarkTaskFamily,
    MixedBenchmarkCase,
    MixedBenchmarkCaseResult,
    MixedBenchmarkReport,
    MixedBenchmarkSuite,
    StrongRegressionRunRef,
    MicroExpertAdvice,
    MicroExpertBenchmarkReport,
    MicroExpertBenchmarkResult,
    EscalationBudgetEvidence,
    EscalationTraceReport,
    RankedRetrievalSource,
    RetrievalTierEvidence,
    SynthesisResult,
    VerifiedRetrievalResult,
    MathBenchmarkCaseResult,
    MathExpertEvidence,
    MathReasoningAdvice,
    MathSolverKind,
    MathSolverRequest,
    MathSolverResult,
    MediaExpertEvidence,
    ExpertEfficiencyMeasurement,
    PowerSample,
    build_efficiency_report,
    EvolutionAction,
    ExpertEvolutionProposal,
    ExpertEvolutionReport,
    ExpertPerformanceSlice,
    Phase9ExitEvidence,
)
from fam_os.memory import (
    MemoryContentDigest,
    MemoryProvenance,
    MemoryRecordKind,
    MemoryRecordManifest,
    MemoryScope,
    MemorySensitivity,
    MemorySourceKind,
    MemoryDeletionReason,
    MemoryDeletionReceipt,
    MemoryDeletionRequest,
    MemoryExpiryEvaluation,
    MemoryExpiryState,
    MemoryAccessContext,
    DocumentIndexApproval,
    DocumentIndexEvidence,
    DocumentRetrievalHit,
    IndexedDocumentChunk,
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    DocumentIndexReceipt,
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
    DocumentInspection,
    DocumentManagementOperation,
    DocumentManagementReceipt,
    MemoryRelevanceDecision,
    MemoryRejection,
    MemoryRetrievalCandidate,
    MemoryDocumentExport,
    MemoryManagementEvidence,
    MemoryEncryptionEvidence,
    MemoryQualityCase,
    MemoryQualityPrivacyReport,
    Phase10ExitEvidence,
)
from fam_os.adaptation import (
    LocalOutcomePredictor, PreferenceKey, PreferenceResetReceipt, UserPreference,
    UserPreferenceProfile, VerifiedOutcomeObservation,
    OperatingState, OperatingStatePolicy,
    AdaptationDriftPolicy, AdaptationSnapshot,
    Phase11ExitEvidence,
    VerifiedLearningOutcome,
    LiveAdaptationSnapshot,
    ModelPrewarmReceipt,
    ModelPrewarmSource,
    ModelPrewarmStatus,
    AdaptationControlOperation,
    AdaptationControlStatus,
    AdaptationHealthSample,
    AdaptationHealthSummary,
    AdaptationInferenceObservation,
    AdaptationRuntimeHealth,
    LiveAdaptationControlReceipt,
    LiveAdaptationControlRequest,
    LiveAdaptationControlState,
    LiveAdaptationDriftReport,
    WorkflowAdaptationSelection,
)
from fam_os.fabric import (
    DeviceEnrollmentChallenge, DeviceEnrollmentRecord, DeviceEnrollmentRequest,
    DeviceIdentity, DevicePairingApproval, DevicePairingOffer, PeerEndpoint,
    AuthenticatedPeer,
    PeerEnrollmentRecord, PeerEnrollmentState,
    PeerControlOperation, PeerControlRequest, PeerControlResponse, PeerControlStatus,
    PeerServiceConfiguration,
    PeerCapabilityDeclaration, PeerManagementOperation, PeerManagementReceipt,
    PeerManagementRequest, PeerPerformanceObservation, PeerPrivacyPolicyRecord,
    TrustedPeerDirectoryEntry,
    RemoteContextDirection, RemoteContextDisclosureEvidence,
    RemoteContextEnvelope, RemoteContextReceipt, RemoteContextReceiptStatus,
    RemoteContextSendRequest, RemoteRawContextFragment, RemoteRawContextKind,
    RemoteTaskDescriptor, remote_context_payload,
    RemoteExecutionAuthority, RemoteExecutionPlan, RemoteExecutionRequest,
    RemoteEvidenceDisposition, RemoteExecutionEvidence, RemoteExecutionResult,
    RemoteExecutionStatus, RemoteVerificationOutcome, RemoteAttemptFailure,
    RemoteRecoveryDisposition, RemoteRecoveryEvidence,
    HardwareAnchorKind, PhysicalHostEvidence, PhysicalHostRole,
    PhysicalPeerCheckpoint, PhysicalPeerObservation,
    RemoteContextRequest, RemoteContextSensitivity, RemoteExpertCapability,
    RemotePrivacyDecision, RemotePrivacyPolicy,
    FabricEncryptedEnvelope, FabricHandshake, FabricRecoveryDecision,
    FabricRouteCandidate, FabricRouteDecision, RemoteFailureKind,
    MultiDeviceDemoReport,
)
from fam_os.expert_factory import (
    AdapterTrainingMethod, AdapterTrainingPlan, AdapterTrainingRecipe,
    ConversionOutputType, ConversionStatus,
    ApprovedBaseModel, DatasetLeakageFinding, DatasetLeakageKind,
    DatasetPartition, DatasetSplitPolicy, DistillationPlan,
    EvaluationCaseKind, EvaluationPlan, ExampleReviewKind,
    FactoryLifecycleReport, FactoryTrainingApproval,
    FactoryCapabilityProposal,
    FailureTrace, FailureTraceCluster, HardwareTrainingMetrics, MissingCapabilityProposal,
    PublishedExpertPackage, QuantizedVariant, RegressionGateResult,
    SyntheticExampleReview, TeacherDataset,
    TrainingApprovalConsumption, TrainingApprovalRevocation,
    TrainingCaptureGrant, TrainingCaptureRevocation, TrainingComputeDtype,
    TrainingDataSensitivity, TrainingResourceBudget, TrainingSourceKind,
    TrainingTerminalStatus,
    VerifiedFailureCluster, VerifiedFailureTrace,
    build_captured_source, build_synthetic_example,
    build_evaluation_approval, build_evaluation_policy,
    build_evaluation_report, build_held_out_access_receipt,
    build_paired_measurement, decide_comparison,
    build_conversion_approval, build_conversion_environment,
    build_conversion_receipt,
    build_specialist_package_receipt, build_specialist_release_lineage,
    FactorySpecialistLifecycleAction,
    build_specialist_lifecycle_receipt, build_specialist_lifecycle_request,
    FactoryCanaryStatus, build_canary_approval, build_canary_report,
    decide_canary_activation,
    build_sealed_dataset_blob_receipt, build_verified_failure_trace,
    build_training_environment, build_training_job,
    build_training_terminal_receipt, discover_failure_clusters,
    build_resource_snapshot, decide_training_admission, seal_factory_dataset,
    train_micro_expert, LabeledExample,
)
from fam_os.console.contracts import ConsoleItem, ConsoleSection, ConsoleSnapshot
from fam_os.product.benchmark_publication import (
    BenchmarkPublication, ProfileBenchmarkSummary,
)
from fam_os.product.integration_coverage import (
    IntegrationCoverageItem,
    IntegrationCoverageManifest,
    IntegrationMaturity,
    IntegrationProgramStatus,
)
from fam_os.product.linux_installation import InstallationReceipt
from fam_os.product.phase14_exit import Phase14ExitEvidence
from fam_os.product.phase15_exit import Phase15ExitEvidence
from fam_os.product.recovery_mode import RecoveryDecision, RecoveryOperation
from fam_os.product.restart_recovery import (
    PersistedActionRecord,
    PersistedActionState,
    restart_decision,
)
from fam_os.product.request_recovery import (
    RecoverableRequestState,
    RequestRecoveryRecord,
    RequestWorkKind,
    request_restart_decision,
)
from fam_os.product.worker_budgets import (
    WorkerBudgetPolicy,
    WorkerBudgetShare,
    WorkerKind,
    derive_worker_limits,
)
from fam_os.product.soak_contracts import SoakReport
from fam_os.product.update_contracts import (
    ComponentKind,
    ReleaseComponent,
    SignedReleaseManifest,
    UpdateReceipt,
)
from fam_os.core.production import (
    ApplicationExecutionRecord,
    ApplicationExecutionState,
    AssuranceLevel,
    InferenceExecutionRecord,
    InferenceExecutionState,
    ModelIntent,
    RuntimeModelEntry,
    RuntimeModelSelection,
)
from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import TaskRequest
from fam_os.telemetry import InferenceMetrics
from fam_os.core.routing import RoutedTaskRequest
from fam_os.routing import RouteDecision, RouteName, RoutingResult
from fam_os.security.review import FindingDisposition, SecurityReviewReport
from fam_os.registry import ArtifactDigest, PackageMetadata, PackageTrustLevel
from fam_os.registry import (
    BuiltInPackageAnchor,
    PackageSignature,
    PackageTrustPolicy,
    PackageValidationReport,
    SignatureAlgorithm,
    TrustedPublisherKey,
)
from fam_os.registry.lifecycle_contracts import (
    ExpertPackageInstallationState,
    InstalledExpertPackage,
    PackageLifecycleAction,
    PackageLifecycleEvent,
)
from fam_os.experts import ExpertPackageCoordinate
import base64
import hashlib
from fam_os.scheduler.resources import (
    AcceleratorKind,
    AcceleratorResourceBudget,
    CpuResourceBudget,
    EffectiveResourceBudget,
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    HostAcceleratorInventory,
    HostCpuInventory,
    HostInventory,
    HostMemoryInventory,
    HostStorageInventory,
    MemoryResourceBudget,
    PressureReading,
    StorageMedium,
    StorageResourceBudget,
    ValidationProfilePurpose,
    ValidationProfileRef,
)
from fam_os.verification import (
    DeterminismClass,
    ExactTextVerification,
    MediaArtifactTextReport,
    VerificationDeclaration,
    VerificationDeclarationV1Alpha1,
    VerificationFact,
    VerificationRunRecord,
    VerificationStatus,
    VerifierActivationDecision,
    VerifierManifest,
    VerifierRuntimeBinding,
    VerifierTrustPolicy,
    contract_for_kind,
)
from fam_os.verification.python.quality import (
    AnalyzerResult,
    PythonQualityReport,
    QualityGateStatus,
)
from fam_os.verification.language_quality import (
    LanguageGateEvidence,
    LanguageGateStatus,
    LanguageQualityReport,
)
from fam_os.verification.math_contracts import MathVerificationReport, MathVerificationRequest
from fam_os.verification.retrieval import (
    RetrievalCitation, RetrievalClaim, RetrievalVerificationReport, RetrievedSource,
)
from fam_os.core.lifecycle.global_budget import (
    AttemptBudgetReservation,
    GlobalAttemptBudget,
    GlobalAttemptBudgetSnapshot,
)
from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from tests.contract.schema_application_fixtures import (
    NOW,
    action_proposal,
    capability,
    observation_result,
)


GIB = 1024**3


def package(package_id: str) -> PackageMetadata:
    return PackageMetadata(
        package_id,
        "1.0.0",
        "publisher.fam",
        "Apache-2.0",
        PackageTrustLevel.BUILT_IN,
        ArtifactDigest("sha256", "a" * 64),
    )


def host_inventory() -> HostInventory:
    return HostInventory(
        "inventory-1",
        NOW,
        "linux",
        "test",
        HostCpuInventory("x86_64", tuple(range(24)), "Test CPU", 16),
        HostMemoryInventory(64 * GIB, 48 * GIB, 8 * GIB, 8 * GIB),
        (HostStorageInventory("nvme-root", StorageMedium.NVME, 2_000 * GIB, 1_000 * GIB, True, "/"),),
        (HostAcceleratorInventory("gpu-0", AcceleratorKind.GPU, "Test GPU", 16 * GIB, "1"),),
    )


def effective_budget() -> EffectiveResourceBudget:
    return EffectiveResourceBudget(
        "budget-1",
        "inventory-1",
        NOW,
        ValidationProfileRef(
            FULL_REFERENCE_WORKSTATION_PROFILE_ID,
            ValidationProfilePurpose.FULL_HOST_CAPABILITY,
        ),
        CpuResourceBudget(tuple(range(24)), tuple(range(20)), tuple(range(20, 24)), 20.0, 0.1),
        MemoryResourceBudget(60 * GIB, 52 * GIB, 8 * GIB, 4 * GIB, 8 * GIB, 0),
        (AcceleratorResourceBudget("gpu-0", True, 15 * GIB, 14 * GIB, GIB, 0),),
        (StorageResourceBudget("nvme-root", 900 * GIB, 800 * GIB, 100 * GIB, 5 * GIB),),
        (PressureReading("cpu", NOW, utilization_fraction=0.1),),
    )


def verifier_manifest() -> VerifierManifest:
    return VerifierManifest(
        package("package.verifier"),
        "verifier.document-hash",
        "Document hash verifier",
        "fam.verifier.runner/v1",
        ("document.hash",),
        ("capability.vscode.edit-output.v1",),
        "evidence.document-hash.v1",
        DeterminismClass.DETERMINISTIC,
        ("isolation.process", "isolation.network-denied"),
        10.0,
    )


def verifier_runtime_binding() -> VerifierRuntimeBinding:
    item = verifier_manifest()
    return VerifierRuntimeBinding(
        item.package.package_id, item.package.package_version, item.verifier_id,
        item.runner_contract_id, "python.subprocess/v1", "fam_verifier:run",
        item.package.artifact_digest,
    )


def verifier_trust_policy() -> VerifierTrustPolicy:
    return VerifierTrustPolicy(
        "verifier-policy", (verifier_manifest().verifier_id,),
        (verifier_manifest().runner_contract_id,), PackageTrustLevel.LOCAL_UNVERIFIED,
    )


def verifier_activation_decision() -> VerifierActivationDecision:
    item = verifier_manifest()
    return VerifierActivationDecision(
        True, "accepted", item.verifier_id, item.package.package_id,
        item.package.package_version, "verifier-policy", item.package.artifact_digest.value,
    )


def python_quality_report() -> PythonQualityReport:
    passed = AnalyzerResult("analyzer", QualityGateStatus.PASSED, 0, "ok")
    return PythonQualityReport("quality-1", passed, passed, passed, passed)


def language_quality_report() -> LanguageQualityReport:
    gate = LanguageGateEvidence("compile", LanguageGateStatus.PASSED, 0, "ok")
    return LanguageQualityReport("language-1", "rust", "rustc test", (gate,))


def math_verification_request() -> MathVerificationRequest:
    return MathVerificationRequest("math-1", "x + 1", "1 + x", "x", ("0", "1"), "1e-20")


def math_verification_report() -> MathVerificationReport:
    return MathVerificationReport("math-1", True, True, "0", None, 50, 2, True)


def retrieval_verification_report() -> RetrievalVerificationReport:
    return RetrievalVerificationReport("retrieval-1", ("claim-1",), (), (), True)


def verification_declaration() -> VerificationDeclaration:
    specification = ExactTextVerification("READY")
    return VerificationDeclaration(
        "declaration-request-1", "request-1",
        contract_for_kind(specification.kind), specification,
    )


def legacy_verification_declaration() -> VerificationDeclarationV1Alpha1:
    specification = ExactTextVerification("READY")
    return VerificationDeclarationV1Alpha1(
        "legacy-declaration-request-1", "legacy-request-1",
        contract_for_kind(specification.kind), specification,
    )


def verification_run() -> VerificationRunRecord:
    declaration = verification_declaration()
    return VerificationRunRecord(
        "verification-1", "request-1", "candidate-1", declaration.declaration_id,
        declaration.contract.verifier_id, declaration.contract.acceptance_id,
        "fam.verifier.text.exact", "1.0.0", "python.in-process/v1",
        "a" * 64, VerificationStatus.PASSED, "accepted",
        (VerificationFact("candidate_sha256", "b" * 64),),
        "signed", "release-1", "key-1", NOW,
    )


def media_verification_report() -> MediaArtifactTextReport:
    return MediaArtifactTextReport(
        "verification-media", "a" * 64, 100, True, True, True, True, "accepted",
    )


def global_attempt_budget_values() -> tuple[object, ...]:
    return (
        GlobalAttemptBudget("plan-instance-1", 4096, 30000, 2, 1),
        AttemptBudgetReservation("reservation-1", "plan-instance-1", "attempt-1", AttemptKind.REPAIR, 1024, 5000),
        GlobalAttemptBudgetSnapshot("plan-instance-1", 1024, 5000, 1, 0, ("reservation-1",)),
    )


def mixed_benchmark_values() -> tuple[object, ...]:
    cases = tuple(
        MixedBenchmarkCase(
            f"case-{family.value}", family, f"capability.{family.value}",
            f"acceptance.{family.value}", "a" * 64,
        )
        for family in BenchmarkTaskFamily
    )
    suite = MixedBenchmarkSuite("mixed", "1", cases)
    results = tuple(
        MixedBenchmarkCaseResult(case.case_id, True, case.acceptance_id, "b" * 64)
        for case in cases
    )
    strong = (
        StrongRegressionRunRef("laguna-xs.2:q4_K_M", "expert.laguna", "c" * 64, "d" * 64, True),
        StrongRegressionRunRef("gemma4:26b", "expert.gemma", "e" * 64, "f" * 64, True),
    )
    return suite, MixedBenchmarkReport("mixed", "1", results, strong, True)


def micro_expert_values() -> tuple[object, ...]:
    advice = MicroExpertAdvice("expert.micro.test", "label", 900_000, ("reason",))
    results = tuple(
        MicroExpertBenchmarkResult(f"expert.micro.{index}", 10, 9, 900_000, "a" * 64)
        for index in range(4)
    )
    return advice, MicroExpertBenchmarkReport("micro", results, 900_000, True)


def escalation_trace() -> EscalationTraceReport:
    budget = EscalationBudgetEvidence(1000, 5000, 0, 1, ("reservation-1",))
    return EscalationTraceReport(
        "trace-1", "small:model", "large:model", "expert.large", "a" * 64,
        ("economical", "escalation"), ("failed", "passed"), "acceptance",
        "b" * 64, "c" * 64, 4000, budget, True, "d" * 64,
    )


def retrieval_tier_values() -> tuple[object, ...]:
    source = RetrievedSource("source-1", "fixture://source-1", "trusted text", "a" * 64, "prov-1")
    ranked = RankedRetrievalSource(source, 0.9, 1.0, 0.92, 1)
    citation = RetrievalCitation("citation-1", "source-1", 0, 7, "b" * 64)
    synthesis = SynthesisResult(
        "trusted", (RetrievalClaim("claim-1", ("citation-1",)),),
        (citation,), "model:small",
    )
    verification = RetrievalVerificationReport(
        "verification-1", ("claim-1",), (), (), True,
    )
    result = VerifiedRetrievalResult(
        "query", (ranked,), synthesis, verification, True,
    )
    evidence = RetrievalTierEvidence(
        "evidence-1", "expert.embed", "embed:model", "c" * 64, 768,
        "expert.rerank", ("source-1",), "expert.synthesis", "model:small",
        "d" * 64, ("source-1",), ("claim-1",), "trusted", True,
    )
    return result, evidence


def math_expert_values() -> tuple[object, ...]:
    advice = MathReasoningAdvice("math-1", "reason", "1+1", "2", "model:small")
    request = MathSolverRequest("math-1", MathSolverKind.EXACT_ARITHMETIC, "1+1")
    result = MathSolverResult("math-1", MathSolverKind.EXACT_ARITHMETIC, "2", "solver", True)
    case = MathBenchmarkCaseResult("math-1", advice, result, "2", True)
    evidence = MathExpertEvidence(
        "math-evidence", "expert.reason", "a" * 64, "expert.solver", "b" * 64,
        (case,), True,
    )
    return advice, request, result, evidence


def media_expert_evidence() -> MediaExpertEvidence:
    return MediaExpertEvidence(
        "media-1", "vision:model", "a" * 64, "description", "OCR", "OCR", True,
        "voice", "b" * 64, "c" * 64, "asr:model", "d" * 64,
        "hello", "hello", True, True,
    )


def efficiency_report():
    samples = (PowerSample(0, 10), PowerSample(1, 12))
    values = (
        ExpertEfficiencyMeasurement("a", "a:model", "a" * 64, .8, 10, 1, 11, samples),
        ExpertEfficiencyMeasurement("b", "b:model", "b" * 64, 1, 20, 2, 22, samples),
    )
    return build_efficiency_report("efficiency-1", "meter", "benchmark", values)


def evolution_values():
    performance = ExpertPerformanceSlice("expert", "code.generate", "python", 18, 20, .02)
    proposal = ExpertEvolutionProposal(
        "proposal", EvolutionAction.SPLIT, ("expert",), ("expert:python",), ("gap",),
    )
    return performance, proposal, ExpertEvolutionReport("evolution", ("benchmark",), (proposal,))


def phase9_exit():
    return Phase9ExitEvidence("phase9", True, 5, 4, ("code",), tuple(f"p{i}" for i in range(8)), True)


def expert_manifest() -> ExpertManifest:
    return ExpertManifest(
        package("package.expert"),
        "expert.code-small",
        "Small code expert",
        ExpertTier.ECONOMICAL,
        ("code.generate",),
        "fam.inference.chat/v1",
        ("weights",),
        ExpertResourceRequirements(2 * GIB, 2 * GIB, 8192, 4 * GIB, supported_architectures=("x86_64",)),
        ("verifier.document-hash",),
    )


def legacy_expert_manifest() -> ExpertManifestV1Alpha1:
    current = expert_manifest()
    return ExpertManifestV1Alpha1(
        current.package,
        current.expert_id,
        current.display_name,
        current.tier,
        current.capabilities,
        current.runtime_contract_id,
        current.artifact_ids,
        current.resources,
        current.required_verifier_ids,
    )


def connector_manifest() -> ConnectorManifest:
    return ConnectorManifest(
        package("package.connector"),
        "connector-vscode",
        "VS Code connector",
        ("app.vscode",),
        (capability(),),
        ("fam.native.vscode", "mcp"),
        (ApplicationAuthority.MODIFY,),
        "sandbox.connector-default",
    )


def memory_record() -> MemoryRecordManifest:
    return MemoryRecordManifest(
        "record-1",
        MemoryRecordKind.DOCUMENT_CHUNK,
        NOW,
        "memory.document-chunk.v1",
        "text/plain",
        4,
        MemoryContentDigest("sha256", "b" * 64),
        MemoryScope("user-1", ("assist",), workspace_ids=("workspace-1",)),
        MemoryProvenance(MemorySourceKind.APPLICATION, "app.vscode", "user-1", NOW),
        MemorySensitivity.PRIVATE,
        "retain-30-days",
        NOW + timedelta(days=30),
    )


def memory_lifecycle_values():
    expiry = MemoryExpiryEvaluation(
        "memory-1", NOW + timedelta(days=1), NOW, MemoryExpiryState.ACTIVE,
    )
    request = MemoryDeletionRequest(
        "delete-1", "memory-1", "user-1", "user-1", NOW,
        MemoryDeletionReason.USER_REQUEST,
    )
    receipt = MemoryDeletionReceipt(
        "delete-1", "memory-1", NOW, "a" * 64, "b" * 64, True,
    )
    access = MemoryAccessContext("user-1", "assist", "app.vscode", "workspace-1", "session-1")
    return expiry, request, receipt, access


def document_index_values():
    approval = DocumentIndexApproval(
        "doc", "fixture://doc", "a" * 64, MemoryScope("user-1", ("assist",)),
        "user-1", NOW, "embed:model", "b" * 64,
    )
    chunk = IndexedDocumentChunk("chunk", "doc", 0, "content", "c" * 64, (1.0, 0.0))
    hit = DocumentRetrievalHit("chunk", "doc", "content", .9, "fixture://doc", "a" * 64)
    evidence = DocumentIndexEvidence(
        "evidence", "doc", "a" * 64, "embed:model", "b" * 64,
        1, "chunk", 0, "d" * 64, True,
    )
    return approval, chunk, hit, evidence


def document_index_grant_values():
    grant = DocumentIndexGrant(
        "grant-1", "/home/user/project", DocumentIndexGrantKind.FOLDER,
        MemoryScope("user-1", ("assist",), workspace_ids=("workspace-1",)),
        True, (".md", ".txt"), 64, 1_048_576, 8_388_608,
        "user-1", NOW, NOW + timedelta(days=7), "embed:model", "b" * 64,
    )
    receipt = DocumentIndexReceipt(
        "receipt-1", "grant-1", ("doc-1",), 2, 128, (),
        NOW, NOW + timedelta(days=7), True,
    )
    return grant, receipt


def memory_relevance_values():
    candidate = MemoryRetrievalCandidate(
        "memory-1", MemoryScope("user-1", ("assist",)), NOW, .8, 20,
    )
    decision = MemoryRelevanceDecision(
        ("memory-1",), 20, (MemoryRejection("memory-2", "memory.stale"),),
    )
    return candidate, decision


def memory_document_export():
    import hashlib
    content_digest = hashlib.sha256(b"content").hexdigest()
    approval = replace(document_index_values()[0], source_sha256=content_digest)
    return MemoryDocumentExport(approval, "content", content_digest)


def memory_management_evidence():
    return MemoryManagementEvidence("management", True, True, True, True, 0, True)


def document_management_values():
    import hashlib
    content_digest = hashlib.sha256(b"content").hexdigest()
    approval = replace(document_index_values()[0], source_sha256=content_digest)
    replacement_digest = hashlib.sha256(b"corrected").hexdigest()
    return (
        DocumentInspection(approval, 1, 7, content_digest),
        DocumentCorrectionRequest(
            "correct-1", approval.document_id, content_digest,
            "corrected", replacement_digest, True,
        ),
        DocumentExpirationRequest("expire-1", "grant-1", True),
        DocumentDeletionRequest("delete-1", approval.document_id, content_digest, True),
        DocumentManagementReceipt(
            "receipt-1", "correct-1", DocumentManagementOperation.CORRECT,
            approval.document_id, "user-1", "user-1", NOW,
            content_digest, replacement_digest, (approval.document_id,),
            "a" * 64, False,
        ),
    )


def memory_encryption_evidence():
    return MemoryEncryptionEvidence("encryption", "AES-256-GCM", True, True, True, "a" * 64, True)


def memory_quality_report():
    case = MemoryQualityCase("query", "doc", "doc", True)
    return MemoryQualityPrivacyReport("quality", (case,), 1.0, 0, 0, True)


def phase10_exit():
    return Phase10ExitEvidence("phase10", True, True, True, 0, 0, 1.0, True)


def outcome_prediction_values():
    observations = (
        VerifiedOutcomeObservation("outcome-a", "workflow", NOW, True, 2048, False, "a" * 64),
        VerifiedOutcomeObservation("outcome-b", "workflow", NOW, True, 4096, True, "b" * 64),
    )
    return (*observations, LocalOutcomePredictor().predict("prediction", "workflow", observations))


def preference_values():
    profile = UserPreferenceProfile("user-1", (
        UserPreference(PreferenceKey.QUALITY_PRIORITY, .8, NOW),
    ))
    receipt = PreferenceResetReceipt("user-1", NOW, (PreferenceKey.QUALITY_PRIORITY,))
    return profile, receipt


def operating_policy_values():
    state = OperatingState(None, None, 50, .1, 600)
    return state, OperatingStatePolicy().decide(state)


def adaptation_drift_values():
    baseline = AdaptationSnapshot("base", "a" * 64, 1, 1, 10)
    candidate = AdaptationSnapshot("candidate", "b" * 64, .9, 1.2, 12)
    policy = AdaptationDriftPolicy()
    report = policy.evaluate(baseline, candidate)
    return baseline, candidate, report, policy.rollback(baseline, candidate, report)


def phase11_exit():
    return Phase11ExitEvidence("phase11", "model", 2, 1, True, True, True, True, True)


def verified_learning_outcome():
    return VerifiedLearningOutcome(
        "verified-learning-fixture", "intent:code", "code", "code:model",
        "specialist", NOW, 2048, False, "acceptance-1", "candidate-1", "a" * 64,
    )


def live_adaptation_values():
    snapshot = LiveAdaptationSnapshot(
        "live-snapshot-fixture", "intent:code", NOW, 2, 2048, .5, False,
        ("code:model",), None, None, ("learning-1", "learning-2"), "b" * 64,
    )
    receipt = ModelPrewarmReceipt(
        "prewarm-fixture", snapshot.snapshot_id, "code:model",
        ModelPrewarmSource.FREQUENCY, ModelPrewarmStatus.COMPLETED,
        NOW, NOW + timedelta(seconds=1), 1000, False, True, 1000,
        ("prediction.supported", "capacity.within_all_bounds", "eviction.none"),
    )
    return snapshot, receipt


def live_adaptation_control_values():
    selection = WorkflowAdaptationSelection("intent:code", "live-snapshot-fixture")
    state = LiveAdaptationControlState(
        1, True, (selection,), (selection,), (), NOW,
        AdaptationControlOperation.ENABLE,
    )
    request = LiveAdaptationControlRequest(
        "adaptation-enable-fixture", AdaptationControlOperation.ENABLE, True,
    )
    receipt = LiveAdaptationControlReceipt(
        "adaptation-control-fixture", request.request_id, request.operation,
        AdaptationControlStatus.APPLIED, NOW, 0, state, None, 0, 0, 0,
        ("adaptation.enabled",),
    )
    health = AdaptationRuntimeHealth(65, True, ("policy.runtime_bounds_satisfied",))
    observation = AdaptationInferenceObservation(
        "inference-observation-fixture", "request-fixture", selection.snapshot_id,
        selection.workflow_id, "code:model", NOW, 1, .1, 100, 20, 2048, 32768,
        health,
    )
    sample = AdaptationHealthSample(
        "health-sample-fixture", observation.observation_id, "c" * 64,
        selection.snapshot_id, selection.workflow_id, observation.model_ref, NOW,
        1, 1, 65, True, ("acceptance.verified",),
    )
    baseline = AdaptationHealthSummary(
        selection.snapshot_id, selection.workflow_id, 2, 1, 1, 65, 2, 0,
        ("sample-a", "sample-b"), "d" * 64,
    )
    candidate = AdaptationHealthSummary(
        "live-snapshot-candidate", selection.workflow_id, 2, 1, .9, 64, 2, 0,
        ("sample-c", "sample-d"), "e" * 64,
    )
    report = LiveAdaptationDriftReport(
        "live-drift-fixture", selection.workflow_id, baseline, candidate,
        ("verification_quality", "latency", "thermal", "policy"), (), (), False, NOW,
    )
    return state, request, receipt, observation, sample, baseline, report


def device_identity_values():
    raw = b"k" * 32
    identity = DeviceIdentity("device", "Device", base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest())
    request = DeviceEnrollmentRequest("request", identity, NOW)
    challenge = DeviceEnrollmentChallenge("request", base64.b64encode(b"n" * 32).decode(), NOW + timedelta(minutes=1))
    record = DeviceEnrollmentRecord(identity, NOW, "owner", True)
    endpoint = PeerEndpoint("peer.example", 48121)
    offer = DevicePairingOffer(
        "pairing", identity, base64.b64encode(b"certificate").decode(), endpoint,
        base64.b64encode(b"n" * 32).decode(), NOW, NOW + timedelta(minutes=10),
        base64.b64encode(b"s" * 64).decode(),
    )
    local_raw = b"l" * 32
    local_identity = DeviceIdentity(
        "local-device", "Local device", base64.b64encode(local_raw).decode(),
        hashlib.sha256(local_raw).hexdigest(),
    )
    approval = DevicePairingApproval(
        "approval", "owner", local_identity, identity,
        offer.identity_certificate_base64, endpoint, "local-offer", offer.request_id,
        "a" * 64, NOW, base64.b64encode(b"s" * 64).decode(),
    )
    authenticated = AuthenticatedPeer(
        identity.device_id, identity.display_name, "owner", "b" * 64, "TLSv1.3",
    )
    enrollment = PeerEnrollmentRecord(
        "enrollment", approval, PeerEnrollmentState.ACTIVE, 1, NOW,
    )
    capability = PeerCapabilityDeclaration(
        "capability", identity.device_id, "expert", "model:q4",
        "specialist", ("code.generate",), 4096, "d" * 64, 1, NOW,
        NOW + timedelta(hours=1), base64.b64encode(b"s" * 64).decode(),
    )
    control_request = PeerControlRequest(
        "peer-control", identity.device_id, PeerControlOperation.HEALTH, NOW,
    )
    control_response = PeerControlResponse(
        control_request.request_id, "local-device", PeerControlStatus.READY,
        NOW, "c" * 64,
    )
    performance = PeerPerformanceObservation(
        "performance", enrollment.enrollment_id, identity.device_id,
        12.5, 1024, NOW, "e" * 64,
    )
    privacy = RemotePrivacyPolicy(
        "owner", (identity.device_id,), ("assist",), ("workspace",),
        4096, (RemoteContextSensitivity.PRIVATE,), False,
    )
    privacy_record = PeerPrivacyPolicyRecord(
        enrollment.enrollment_id, identity.device_id, privacy, 1, NOW,
    )
    management_request = PeerManagementRequest(
        "peer-management", "owner", PeerManagementOperation.SET_PRIVACY,
        enrollment.enrollment_id, 0, True, "owner.configured", privacy,
    )
    management_receipt = PeerManagementReceipt(
        "peer-receipt", management_request.request_id, "owner",
        management_request.operation, enrollment.enrollment_id, "f" * 64,
        0, 1, True, ("owner.configured",), NOW,
    )
    directory = TrustedPeerDirectoryEntry(
        enrollment.enrollment_id, 1, identity.device_id, identity.display_name,
        endpoint, (capability,), performance, privacy_record,
    )
    peer_configuration = PeerServiceConfiguration(
        True, "Device", "0.0.0.0", endpoint.port, endpoint,
    )
    return (
        identity, request, challenge, record, endpoint, offer, approval,
        authenticated, enrollment, control_request, control_response,
        peer_configuration, capability, performance, privacy_record,
        management_request, management_receipt, directory,
    )


def remote_privacy_values():
    capability = RemoteExpertCapability("device", "expert", ("code.generate",), 1000, "a" * 64)
    policy = RemotePrivacyPolicy("owner", ("device",), ("assist",), ("workspace",),
                                 1000, (RemoteContextSensitivity.PRIVATE,), False)
    request = RemoteContextRequest("owner", "device", "assist", "workspace",
                                   RemoteContextSensitivity.PRIVATE, 100, False)
    return capability, policy, request, RemotePrivacyDecision(True, ())


def remote_context_values():
    descriptor = RemoteTaskDescriptor(
        "intent.code", ("code.generate",), "verified", 4096,
    )
    content = "fixture private context"
    fragment = RemoteRawContextFragment(
        "fragment", RemoteRawContextKind.PROMPT, "a" * 64, content,
        hashlib.sha256(content.encode()).hexdigest(),
    )
    payload = remote_context_payload(
        target_expert_id="expert.code", purpose_id="assist",
        workspace_id="workspace", sensitivity=RemoteContextSensitivity.PRIVATE,
        descriptor=descriptor, raw_fragments=(fragment,),
    )
    context = RemoteContextEnvelope(
        "context", "context-request", "device", "local-device", "expert.code",
        "assist", "workspace", RemoteContextSensitivity.PRIVATE, descriptor,
        (fragment,), len(payload), hashlib.sha256(payload).hexdigest(),
        NOW, NOW + timedelta(minutes=2), base64.b64encode(b"s" * 64).decode(),
    )
    receipt = RemoteContextReceipt(
        "context-receipt", context.request_id, context.context_id,
        context.sender_device_id, context.receiver_device_id,
        RemoteContextReceiptStatus.ACCEPTED, context.content_bytes,
        context.content_sha256, 1, NOW, base64.b64encode(b"r" * 64).decode(),
    )
    request = RemoteContextSendRequest(
        context.request_id, "enrollment", context.target_expert_id, "capability",
        1, context.purpose_id, context.workspace_id, context.sensitivity,
        descriptor, (fragment,), True,
    )
    evidence = RemoteContextDisclosureEvidence(
        "context-evidence", request.request_id, "f" * 64,
        request.enrollment_id, context.receiver_device_id,
        RemoteContextDirection.OUTBOUND, context.context_id,
        context.target_expert_id, context.purpose_id, context.workspace_id,
        context.sensitivity, context.content_bytes, context.content_sha256,
        (fragment.content_sha256,), 1, request.capability_declaration_id, receipt,
        ("privacy.approved", "context.receipt_verified"), NOW,
    )
    return descriptor, fragment, context, receipt, request, evidence


def remote_execution_values():
    descriptor, _fragment, context, receipt, _request, _evidence = remote_context_values()
    capability = PeerCapabilityDeclaration(
        "remote-capability", context.receiver_device_id, context.target_expert_id,
        "gemma4:26b", "escalation", descriptor.capability_ids, 4096, "a" * 64, 1,
        NOW, NOW + timedelta(hours=1), base64.b64encode(b"c" * 64).decode(),
    )
    authority = RemoteExecutionAuthority(
        "enrollment", 1, context.purpose_id, context.workspace_id,
        context.sensitivity, 4096, descriptor.maximum_output_bytes, True,
    )
    plan = RemoteExecutionPlan(
        "remote-plan", "instance-remote", context.request_id, "enrollment",
        context.receiver_device_id, context.target_expert_id, capability.model_ref,
        capability.expert_tier, capability.declaration_id, 1,
        context.purpose_id, context.workspace_id,
        context.sensitivity, descriptor, 4096, 12.5,
        ("authority.confirmed", "scheduler.remote"), NOW,
    )
    execution = RemoteExecutionRequest(
        "remote-execution", plan.plan_id, context, capability, 1024, 256,
        False, 0.2, context.issued_at, base64.b64encode(b"q" * 64).decode(),
    )
    content = "READY"
    result = RemoteExecutionResult(
        execution.execution_id, plan.plan_id, context.request_id,
        context.receiver_device_id, "b" * 64, RemoteExecutionStatus.COMPLETED,
        capability.model_ref, content, len(content.encode()),
        hashlib.sha256(content.encode()).hexdigest(), None,
        InferenceMetrics(capability.model_ref, 1.0, 0.1, 20, 2, 2.0),
        receipt, NOW, NOW + timedelta(seconds=1),
        base64.b64encode(b"z" * 64).decode(),
    )
    evidence = RemoteExecutionEvidence(
        evidence_id="remote-evidence",
        instance_id=plan.instance_id,
        request_id=plan.request_id,
        remote_plan_id=plan.plan_id,
        remote_plan_sha256="1" * 64,
        execution_id=execution.execution_id,
        execution_request_sha256="2" * 64,
        execution_result_sha256="3" * 64,
        enrollment_id=plan.enrollment_id,
        peer_device_id=plan.peer_device_id,
        expert_id=plan.expert_id,
        model_ref=plan.model_ref,
        expert_tier=plan.expert_tier,
        capability_declaration_id=plan.capability_declaration_id,
        context_evidence_id="context-evidence",
        context_id=context.context_id,
        context_content_bytes=context.content_bytes,
        context_content_sha256=context.content_sha256,
        context_receipt_sha256="4" * 64,
        budget_reservation_id="budget-remote",
        budget_attempt_id="attempt-remote",
        candidate_id="candidate-remote",
        candidate_sha256=result.content_sha256,
        result_content_bytes=result.content_bytes,
        result_content_sha256=result.content_sha256,
        disposition=RemoteEvidenceDisposition.AUTHENTICATED_CANDIDATE,
        verification_outcome=RemoteVerificationOutcome.PENDING,
        acceptance_id=None,
        acceptance_evidence_id=None,
        verification_run_id=None,
        authenticated_at=result.completed_at,
        finalized_at=None,
    )
    recovery = RemoteRecoveryEvidence(
        "remote-recovery", plan.instance_id, plan.request_id, plan.plan_id,
        "budget-remote", "attempt-remote", RemoteAttemptFailure.DISCONNECTED,
        "5" * 64, "5" * 64, True, True,
        "selection-local", "local:q4", "economical",
        "budget-local-recovery", "attempt-local-recovery", None,
        RemoteRecoveryDisposition.LOCAL_RETRY_PENDING,
        ("remote.disconnected", "acceptance.unchanged", "fallback.local"),
        NOW, None,
    )
    physical_public_key = b"f" * 32
    physical_fingerprint = hashlib.sha256(physical_public_key).hexdigest()
    physical = PhysicalHostEvidence(
        "physical-host-requester", "qualification-1", PhysicalHostRole.REQUESTER,
        "device-" + physical_fingerprint[:24],
        base64.b64encode(physical_public_key).decode("ascii"), physical_fingerprint,
        "6" * 64, HardwareAnchorKind.DMI_PRODUCT_UUID, "7" * 64, "8" * 64,
        "6.8.0", "x86_64", "none", True, 24, 64 * 1024**3,
        2 * 1024**4, 1, ("9" * 64,), "release-1", "signer-1", "a" * 64,
        7, True, NOW, base64.b64encode(b"s" * 64).decode("ascii"),
    )
    peer_observation = PhysicalPeerObservation(
        "peer-observation-1", "qualification-1",
        PhysicalPeerCheckpoint.BEFORE_REMOTE_SUCCESS,
        "device-" + physical_fingerprint[:24],
        base64.b64encode(physical_public_key).decode("ascii"),
        physical_fingerprint, 0, 1, "b" * 64, False, NOW,
        base64.b64encode(b"o" * 64).decode("ascii"),
    )
    return (
        authority, plan, execution, result, evidence, recovery, physical,
        peer_observation,
    )


def fabric_transport_values():
    handshake = FabricHandshake("device", "a2V5", "c2ln")
    envelope = FabricEncryptedEnvelope("session", 1, "bm9uY2U=", "Y2lwaGVy")
    candidate = FabricRouteCandidate("device", "expert", False, 10, 2, True, True)
    decision = FabricRouteDecision("device", "expert", 12, ("device",))
    recovery = FabricRecoveryDecision(RemoteFailureKind.DISCONNECTED, True, True, True,
                                      ("remote.disconnected", "fallback.local"))
    demo = MultiDeviceDemoReport("demo", ("desktop", "laptop", "server"), True,
                                 "server", 0, True, True, True)
    return handshake, envelope, candidate, decision, recovery, demo


def expert_factory_values():
    trace = FailureTrace("trace", "routing.classify", "requirement", "verifier", "a" * 64, True)
    cluster = FailureTraceCluster("cluster", "routing.classify", "requirement", ("trace",), ("a" * 64,))
    missing = MissingCapabilityProposal("missing", "routing.classify", "cluster", 2)
    dataset = TeacherDataset("dataset", "teacher", 10, "b" * 64, "Apache-2.0")
    distill = DistillationPlan("distill", dataset, "fam.micro/v1", 2, .2)
    adapter = AdapterTrainingPlan("adapter", "base", "routing.classify", 4, 100)
    evaluation = EvaluationPlan("eval", "acceptance", "c" * 64, .9, "baseline")
    trained = train_micro_expert("micro", "routing.classify", "fam.micro/v1", (
        LabeledExample("code", "code"), LabeledExample("text", "language")))
    metrics = HardwareTrainingMetrics(1, 10, 100, .1, 1)
    variant = QuantizedVariant("q4", "micro", "int4", 4, "d" * 64, 10, "e" * 64, 1, .05, True)
    published = PublishedExpertPackage("package", "f" * 64, "c2ln", "key", "package.json", True)
    gate = RegressionGateResult("gate", .9, 1, 1, .1, 10, 1, True, True, ())
    lifecycle = FactoryLifecycleReport("lifecycle", True, True, True, True, True, True,
                                       True, True, True, "a" * 64, "b" * 64, "gate", True)
    verified_trace = build_verified_failure_trace(
        verification_id="verification-factory-1", request_id="request-factory-1",
        candidate_id="candidate-factory-1", capability_id="intent.code",
        failed_requirement_id="acceptance.python.tests",
        verifier_id="python.deterministic-tests.v1",
        verifier_artifact_sha256="1" * 64, candidate_sha256="2" * 64,
        model_ref="qwen3:1.7b", expert_tier="economical",
        release_id="release-1", signer_key_id="key-1", observed_at=NOW,
    )
    verified_cluster, factory_proposals = discover_failure_clusters((
        verified_trace,
        build_verified_failure_trace(
            verification_id="verification-factory-2",
            request_id="request-factory-2", candidate_id="candidate-factory-2",
            capability_id="intent.code",
            failed_requirement_id="acceptance.python.tests",
            verifier_id="python.deterministic-tests.v1",
            verifier_artifact_sha256="1" * 64,
            candidate_sha256="3" * 64, model_ref="qwen3:1.7b",
            expert_tier="economical", release_id="release-1",
            signer_key_id="key-1", observed_at=NOW,
        ),
    ))
    production_values: tuple[
        VerifiedFailureTrace, VerifiedFailureCluster, FactoryCapabilityProposal,
    ] = (verified_trace, verified_cluster[0], factory_proposals[0])
    split = DatasetSplitPolicy("factory-split-v1", "4" * 64)
    grant = TrainingCaptureGrant(
        "capture-grant-1", factory_proposals[0].proposal_id, "intent.code",
        (TrainingSourceKind.VERIFIED_FIXTURE,), ("workspace:test",),
        (TrainingDataSensitivity.PRIVATE,), 1_000_000, 100, NOW,
        NOW + timedelta(hours=1), True,
    )
    source_family = next(
        f"source-family-{index}" for index in range(100)
        if split.assign(f"source-family-{index}") is not DatasetPartition.HELD_OUT
    )
    captured = build_captured_source(
        source_id="dataset-source-1", grant_id=grant.grant_id,
        proposal_id=grant.proposal_id, source_family_id=source_family,
        split_policy=split, source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
        workspace_scope="workspace:test",
        sensitivity=TrainingDataSensitivity.PRIVATE, license_id="owner-approved",
        input_text="Write a stable ordering function.",
        reference_output="Use input order for equal-priority nodes.", captured_at=NOW,
    )
    synthetic = build_synthetic_example(
        source=captured, teacher_model_ref="gemma4:26b",
        teacher_manifest_sha256="5" * 64,
        input_text="Order equal priority nodes.",
        completion="Preserve the original input order.", generated_at=NOW,
        ordinal=1,
    )
    review = SyntheticExampleReview(
        f"synthetic-review-{synthetic.example_id}", synthetic.example_id,
        ExampleReviewKind.DETERMINISTIC, "python.deterministic-tests.v1",
        "acceptance.python.tests", "6" * 64, True, NOW,
    )
    revocation = TrainingCaptureRevocation(
        "capture-revocation-capture-grant-1-2", grant.grant_id, 1, 2,
        "owner.revoked", NOW,
    )
    sealed_sources = tuple(
        build_captured_source(
            source_id=f"sealed-source-{partition.value}",
            grant_id=grant.grant_id, proposal_id=grant.proposal_id,
            source_family_id=next(
                f"sealed-{partition.value}-family-{index}"
                for index in range(10_000)
                if split.assign(
                    f"sealed-{partition.value}-family-{index}",
                ) is partition
            ),
            split_policy=split,
            source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
            workspace_scope="workspace:test",
            sensitivity=TrainingDataSensitivity.PRIVATE,
            license_id="owner-approved",
            input_text=f"Unique {partition.value} input.",
            reference_output=f"Unique {partition.value} output.",
            captured_at=NOW,
        )
        for partition in DatasetPartition
    )
    sealed_dataset, leakage_report = seal_factory_dataset(
        dataset_id="sealed-dataset-1", proposal_id=grant.proposal_id,
        capability_id=grant.capability_id, sources=sealed_sources,
        examples=(), reviews=(), sealed_at=NOW,
    )
    if sealed_dataset is None:
        raise AssertionError("schema fixture dataset must pass leakage checks")
    leakage_finding = DatasetLeakageFinding(
        "dataset-leakage-fixture", DatasetLeakageKind.EXACT_CROSS_PARTITION,
        "sealed-source-train", "sealed-source-held-out", 1_000_000,
    )
    blob_receipt = build_sealed_dataset_blob_receipt(
        blob_id=sealed_dataset.partitions[0].blob_id,
        dataset_id=sealed_dataset.dataset_id,
        partition=sealed_dataset.partitions[0].partition,
        plaintext_sha256=sealed_dataset.partitions[0].ordered_records_sha256,
        ciphertext_sha256="8" * 64, plaintext_bytes=100,
        ciphertext_bytes=200,
        relative_path=f"blobs/aa/{sealed_dataset.partitions[0].blob_id}.blob",
        created_at=NOW,
    )
    base_model = ApprovedBaseModel(
        "Qwen/Qwen3-1.7B", "1" * 40, "Qwen/Qwen3-1.7B", "2" * 40,
        "Apache-2.0", "7" * 64,
    )
    training_recipe = AdapterTrainingRecipe(
        "qwen3-1.7b-qlora-v1", AdapterTrainingMethod.QLORA, 16, 32, .05,
        ("all-linear",), 4, "nf4", True, TrainingComputeDtype.BFLOAT16,
        2048, 3, 10_000, 1, 16, .0002, 42,
    )
    training_budget = TrainingResourceBudget(
        "training-budget-1", 16, 48 * GIB, 15 * GIB, 200 * GIB, 82,
        10_000_000, "workers.full.v1",
    )
    training_approval = FactoryTrainingApproval(
        "training-approval-1", factory_proposals[0].proposal_id, "intent.code",
        sealed_dataset.dataset_id, sealed_dataset.manifest_sha256,
        sealed_dataset.license_ids, sealed_dataset.sensitivities,
        base_model, training_recipe,
        training_budget, "9" * 64, 7200, 10 * GIB, 2 * GIB,
        "training-job-1", NOW, NOW + timedelta(hours=1), True,
    )
    consumption = TrainingApprovalConsumption(
        "training-consumption-training-approval-1", training_approval.approval_id,
        training_approval.one_use_job_id, 1, NOW,
    )
    training_revocation = TrainingApprovalRevocation(
        "training-revocation-training-approval-1-2",
        training_approval.approval_id, 1, 2, "owner.revoked", NOW,
    )
    training_environment = build_training_environment(
        environment_id="nvidia-qlora-v1", python_version="3.12.3",
        python_executable_sha256="d" * 64,
        platform="linux-x86_64",
        package_versions=(("bitsandbytes", "0.49.2"), ("torch", "2.13.0")),
        wheelhouse_manifest_sha256="e" * 64,
        worker_script_sha256="f" * 64,
        torch_cuda_version="13.0", nvidia_driver_version="595.71.05",
        device_index=0, device_name="NVIDIA GeForce RTX 5080",
        compute_capability="12.0", total_vram_bytes=16 * GIB,
        cuda_available=True, bfloat16_supported=True,
        bitsandbytes_cuda_available=True, incompatibility_reasons=(),
        observed_at=NOW,
    )
    training_job = build_training_job(
        job_id=training_approval.one_use_job_id,
        approval_id=training_approval.approval_id, approval_revision=1,
        approval_consumption_receipt_id=consumption.receipt_id,
        proposal_id=training_approval.proposal_id,
        capability_id=training_approval.capability_id,
        dataset_id=sealed_dataset.dataset_id,
        dataset_manifest_sha256=sealed_dataset.manifest_sha256,
        train_blob_sha256=sealed_dataset.partitions[0].ordered_records_sha256,
        validation_blob_sha256=sealed_dataset.partitions[1].ordered_records_sha256,
        base_model_files_sha256=base_model.files_manifest_sha256,
        environment_sha256=training_environment.manifest_sha256,
        admitted_at=NOW,
    )
    training_terminal = build_training_terminal_receipt(
        receipt_id="training-terminal-1", job_id=training_job.job_id,
        approval_id=training_approval.approval_id,
        environment_sha256=training_environment.manifest_sha256,
        status=TrainingTerminalStatus.COMPLETED,
        reason_code="training.completed", adapter_sha256="a" * 64,
        adapter_config_sha256="b" * 64, adapter_bytes=1024,
        metrics_sha256="c" * 64, started_at=NOW, finished_at=NOW,
        exit_code=0, network_denied=True, held_out_absent=True,
        base_weights_frozen=True, unexpected_trainable_parameters=(),
        peak_ram_bytes=GIB, peak_vram_bytes=GIB,
        maximum_temperature_celsius=60, energy_joules=100,
    )
    resource_snapshot = build_resource_snapshot(
        snapshot_id="training-snapshot-1", logical_cpu_count=24,
        load_fraction=.1, available_ram_bytes=60 * GIB,
        free_disk_bytes=500 * GIB, gpu_total_bytes=16 * GIB,
        gpu_used_bytes=GIB, gpu_utilization_fraction=.05,
        gpu_temperature_celsius=44, inference_conflict=False, observed_at=NOW,
    )
    admission = decide_training_admission(
        decision_id="training-admission-1",
        approval_id=training_approval.approval_id,
        budget=training_budget, snapshot=resource_snapshot, decided_at=NOW,
    )
    evaluation_policy = build_evaluation_policy(
        policy_id="code-specialist-evaluation-v1", capability_id="intent.code",
        minimum_quality_cases=30, minimum_quality_ppm=800_000,
        minimum_improvement_ppm=100_000, confidence_z_ppm=1_960_000,
        maximum_unrelated_regression_ppm=0,
        maximum_p95_latency_microseconds=5_000_000,
        maximum_latency_regression_ppm=200_000,
        maximum_peak_ram_bytes=8 * GIB, maximum_peak_vram_bytes=8 * GIB,
        maximum_energy_joules=10_000, maximum_resource_regression_ppm=200_000,
        maximum_adapter_bytes=100_000_000,
        maximum_cold_start_microseconds=10_000_000,
        require_scheduler_compatibility=True,
    )
    evaluation_approval = build_evaluation_approval(
        approval_id="factory-evaluation-approval-1",
        proposal_id=training_approval.proposal_id,
        capability_id=training_approval.capability_id,
        training_receipt_id=training_terminal.receipt_id,
        adapter_sha256=training_terminal.adapter_sha256,
        adapter_config_sha256=training_terminal.adapter_config_sha256,
        sealed_dataset_id=sealed_dataset.dataset_id,
        sealed_dataset_sha256=sealed_dataset.manifest_sha256,
        held_out_blob_id=sealed_dataset.partitions[2].blob_id,
        held_out_blob_sha256=sealed_dataset.partitions[2].ordered_records_sha256,
        incumbent_expert_id="qwen3-1.7b-base",
        incumbent_artifact_sha256=base_model.files_manifest_sha256,
        suite_sha256="1" * 64,
        evaluator_environment_sha256=training_environment.manifest_sha256,
        evaluator_script_sha256="2" * 64,
        policy=evaluation_policy, one_use_evaluation_id="factory-evaluation-1",
        issued_at=NOW, expires_at=NOW + timedelta(hours=1),
    )
    held_out_access = build_held_out_access_receipt(
        receipt_id="held-out-access-1",
        approval_id=evaluation_approval.approval_id,
        evaluation_id=evaluation_approval.one_use_evaluation_id,
        dataset_id=sealed_dataset.dataset_id,
        held_out_blob_id=evaluation_approval.held_out_blob_id,
        held_out_blob_sha256=evaluation_approval.held_out_blob_sha256,
        evaluator_environment_sha256=evaluation_approval.evaluator_environment_sha256,
        plaintext_bytes=1024, plaintext_discarded=True, accessed_at=NOW,
    )
    evaluation_measurements = tuple(
        build_paired_measurement(
            measurement_id=f"factory-measurement-{index}",
            evaluation_id=evaluation_approval.one_use_evaluation_id,
            case_id=f"factory-case-{index}", kind=EvaluationCaseKind.QUALITY,
            requirement_id="acceptance.python.tests",
            input_sha256=f"{index % 10}" * 64,
            expected_sha256=f"{(index + 1) % 10}" * 64,
            baseline_output_sha256="3" * 64,
            candidate_output_sha256="4" * 64,
            baseline_passed=False, candidate_passed=True,
            baseline_latency_microseconds=1_000_000,
            candidate_latency_microseconds=1_100_000,
            baseline_peak_ram_bytes=2 * GIB,
            candidate_peak_ram_bytes=2 * GIB,
            baseline_peak_vram_bytes=3 * GIB,
            candidate_peak_vram_bytes=3 * GIB,
            baseline_energy_millijoules=1000,
            candidate_energy_millijoules=1100, measured_at=NOW,
        )
        for index in range(30)
    )
    evaluation_report = build_evaluation_report(
        report_id="factory-evaluation-report-1",
        approval_id=evaluation_approval.approval_id,
        evaluation_id=evaluation_approval.one_use_evaluation_id,
        policy=evaluation_policy,
        evaluator_environment_sha256=evaluation_approval.evaluator_environment_sha256,
        evaluator_script_sha256=evaluation_approval.evaluator_script_sha256,
        held_out_access_receipt_sha256=held_out_access.receipt_sha256,
        network_denied=True, measurements=evaluation_measurements,
        candidate_adapter_bytes=training_terminal.adapter_bytes,
        candidate_cold_start_microseconds=2_000_000,
        scheduler_compatible=True, started_at=NOW, finished_at=NOW,
    )
    comparison_decision = decide_comparison(
        decision_id="factory-comparison-decision-1",
        approval=evaluation_approval, report=evaluation_report, decided_at=NOW,
        signer_key_id="factory-evaluator-1",
        signing_key=Ed25519PrivateKey.from_private_bytes(b"e" * 32),
    )
    conversion_environment = build_conversion_environment(
        environment_id="llama-cpp-conversion-v1",
        llama_cpp_revision="1" * 40,
        convert_hf_script_sha256="2" * 64,
        convert_lora_script_sha256="3" * 64,
        wheelhouse_manifest_sha256="4" * 64,
        python_executable_sha256="5" * 64,
        package_versions=(("torch", "2.11.0+cpu"), ("transformers", "4.57.6")),
        ollama_version="0.13.5", observed_at=NOW,
    )
    conversion_approval = build_conversion_approval(
        approval_id="conversion-approval-1",
        evaluation_id=evaluation_approval.one_use_evaluation_id,
        comparison_decision_id=comparison_decision.decision_id,
        comparison_decision_sha256=comparison_decision.decision_sha256,
        adapter_sha256=evaluation_approval.adapter_sha256,
        base_model_sha256=evaluation_approval.incumbent_artifact_sha256,
        environment_sha256=conversion_environment.manifest_sha256,
        base_output_type=ConversionOutputType.BF16,
        adapter_output_type=ConversionOutputType.F16,
        runtime_model_ref="fam-code-specialist:canary",
        maximum_output_bytes=8_000_000_000,
        maximum_wall_seconds=3600, maximum_ram_bytes=32 * 1024**3,
        maximum_cpu_cores=12,
        one_use_conversion_id="conversion-1", issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    conversion_receipt = build_conversion_receipt(
        receipt_id="conversion-receipt-1",
        approval_id=conversion_approval.approval_id,
        conversion_id=conversion_approval.one_use_conversion_id,
        comparison_decision_sha256=comparison_decision.decision_sha256,
        environment_sha256=conversion_environment.manifest_sha256,
        status=ConversionStatus.COMPLETED, reason_code="conversion.completed",
        base_gguf_sha256="6" * 64, base_gguf_bytes=4_000_000_000,
        adapter_gguf_sha256="7" * 64, adapter_gguf_bytes=30_000_000,
        modelfile_sha256="8" * 64,
        runtime_model_ref=conversion_approval.runtime_model_ref,
        network_denied=True, started_at=NOW, finished_at=NOW,
    )
    release_lineage = build_specialist_release_lineage(
        release_id="specialist-release-1", package_id="fam.specialist.code-1",
        package_version="1.0.0", expert_id="expert.specialist.code-1",
        training_capability_id="intent.code",
        declared_capabilities=("code.generate.python", "code.repair.python"),
        required_verifier_ids=("python.deterministic-tests.v1",),
        conversion_receipt_id=conversion_receipt.receipt_id,
        conversion_receipt_sha256=conversion_receipt.receipt_sha256,
        conversion_environment_sha256=conversion_environment.manifest_sha256,
        comparison_decision_id=comparison_decision.decision_id,
        comparison_decision_sha256=comparison_decision.decision_sha256,
        training_receipt_id=training_terminal.receipt_id,
        sealed_dataset_id=sealed_dataset.dataset_id,
        sealed_dataset_sha256=sealed_dataset.manifest_sha256,
        base_model_id=base_model.repository_id,
        base_model_revision=base_model.revision,
        base_model_files_sha256=base_model.files_manifest_sha256,
        adapter_sha256=training_terminal.adapter_sha256,
        base_gguf_sha256=conversion_receipt.base_gguf_sha256,
        adapter_gguf_sha256=conversion_receipt.adapter_gguf_sha256,
        modelfile_sha256=conversion_receipt.modelfile_sha256,
        tokenizer_sha256="9" * 64, chat_template_sha256="a" * 64,
        merge_policy="runtime_lora_adapter",
        base_output_type=conversion_approval.base_output_type,
        adapter_output_type=conversion_approval.adapter_output_type,
        runtime_model_ref=conversion_approval.runtime_model_ref,
        license_id=base_model.license_id,
        estimated_resident_bytes=4_030_000_000,
        storage_bytes=4_030_000_000, max_context_tokens=8192,
        minimum_system_memory_bytes=8 * GIB,
        minimum_accelerator_memory_bytes=4 * GIB,
        accelerator_optional=True, supported_architectures=("x86_64",),
        created_at=NOW,
    )
    package_receipt = build_specialist_package_receipt(
        receipt_id="specialist-package-receipt-1",
        release_id=release_lineage.release_id,
        package_id=release_lineage.package_id,
        package_version=release_lineage.package_version,
        lineage_sha256=release_lineage.lineage_sha256,
        artifact_sha256="b" * 64, expert_manifest_sha256="c" * 64,
        runtime_binding_sha256="d" * 64, signature_sha256="e" * 64,
        signature_key_id="factory-release-key-1",
        validation_policy_id="factory-release-policy-1",
        compatibility_sha256="f" * 64,
        artifact_locator="packages/fam.specialist.code-1-1.0.0.tar",
        lifecycle_revision=1, installed_disabled=True, installed_at=NOW,
    )
    canary_approval = build_canary_approval(
        approval_id="canary-approval-1", release_id=release_lineage.release_id,
        package_receipt_sha256=package_receipt.receipt_sha256,
        package_id=release_lineage.package_id,
        package_version=release_lineage.package_version,
        expert_id=release_lineage.expert_id,
        runtime_model_ref=release_lineage.runtime_model_ref,
        capability_id=release_lineage.training_capability_id,
        verifier_id=release_lineage.required_verifier_ids[0],
        suite_sha256="1" * 64, case_count=2, maximum_output_tokens=512,
        maximum_wall_seconds=300, maximum_ram_bytes=16 * GIB,
        maximum_vram_bytes=15 * GIB, one_use_canary_id="canary-1",
        issued_at=NOW, expires_at=NOW + timedelta(hours=1),
    )
    canary_report = build_canary_report(
        report_id="canary-report-1", approval_id=canary_approval.approval_id,
        canary_id=canary_approval.one_use_canary_id,
        package_receipt_sha256=canary_approval.package_receipt_sha256,
        suite_sha256=canary_approval.suite_sha256,
        runtime_manifest_sha256="2" * 64,
        status=FactoryCanaryStatus.COMPLETED,
        reason_code="canary.completed", case_count=2, passed_case_count=2,
        verifier_failure_count=0,
        scheduler_selected_declared_capability=True,
        scheduler_excluded_unrelated_capabilities=True,
        outputs_discarded=True, peak_ram_bytes=4 * GIB,
        peak_vram_bytes=4 * GIB, started_at=NOW, finished_at=NOW,
    )
    activation_decision = decide_canary_activation(
        decision_id="canary-activation-1", approval=canary_approval,
        report=canary_report, signer_key_id="factory-canary-key-1",
        signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
        decided_at=NOW,
    )
    lifecycle_request = build_specialist_lifecycle_request(
        request_id="specialist-rollback-request-1",
        action=FactorySpecialistLifecycleAction.MANUAL_ROLLBACK,
        release_id=release_lineage.release_id,
        target_release_id="specialist-known-good-1",
        expected_lifecycle_revision=1,
        reason_code="owner.requested.rollback",
        regression_evidence_sha256=None,
        remove_artifact=False,
        issued_at=NOW,
    )
    lifecycle_receipt = build_specialist_lifecycle_receipt(
        receipt_id="specialist-rollback-receipt-1",
        request_id=lifecycle_request.request_id,
        request_sha256=lifecycle_request.request_sha256,
        action=lifecycle_request.action,
        release_id=lifecycle_request.release_id,
        target_release_id=lifecycle_request.target_release_id,
        reason_code=lifecycle_request.reason_code,
        lifecycle_revision=2,
        active_release_id=lifecycle_request.target_release_id,
        runtime_model_removed=True,
        artifact_removed=False,
        audit_retained=True,
        completed_at=NOW,
    )
    return (
        trace, cluster, missing, *production_values, split, grant, revocation,
        captured, synthetic, review, *sealed_dataset.partitions, leakage_finding,
        leakage_report, sealed_dataset, blob_receipt, base_model, training_recipe,
        training_budget,
        training_approval, consumption, training_revocation,
        training_environment, training_job, training_terminal,
        resource_snapshot, admission, evaluation_policy, evaluation_approval,
        held_out_access, evaluation_measurements[0], evaluation_report,
        comparison_decision, conversion_environment, conversion_approval,
        conversion_receipt, release_lineage, package_receipt, canary_approval,
        canary_report, activation_decision, lifecycle_request, lifecycle_receipt,
        dataset, distill, adapter, evaluation,
        trained, metrics, variant, published, gate, lifecycle,
    )


def product_values():
    review = SecurityReviewReport("review", False, ("bandit",), (("bandit.json", "a" * 64),),
                                  (FindingDisposition("B1", "low", "accepted", "bounded"),), (), True)
    update = UpdateReceipt("v2", "v1", True, True, True, False, "v2", "activated")
    release_manifest = SignedReleaseManifest(
        "v1",
        tuple(
            ReleaseComponent(kind, "payload", f"components/{kind.value}/payload", "a" * 64)
            for kind in ComponentKind
        ),
        "release-key",
        "c2ln",
    )
    recovery = RecoveryDecision(RecoveryOperation.DIAGNOSE, True, False, "bounded_recovery_operation")
    soak = SoakReport("full-reference-workstation", 300, 10, 1, 2, 1, 1000, 10,
                      40960, 0, None, 1, 1, (), True)
    install = InstallationReceipt("/home/user/fam", "v1", (("bin/fam-shell", "b" * 64),),
                                  True, ())
    sections = tuple(ConsoleSection(section_id, section_id.title(), (
        ConsoleItem("state", "State", "Ready", "healthy"),)) for section_id in
        ("resources", "experts", "permissions", "memory", "audit", "recovery"))
    console = ConsoleSnapshot(NOW, 1000, "v1", sections, False)
    minimum = ProfileBenchmarkSummary("compat-cpu-16gb", "cpu.json", "c" * 64,
                                      "passed", (("peak", "1"),), "run cpu")
    full = ProfileBenchmarkSummary("full-reference-workstation", "gpu.json", "d" * 64,
                                   "verified", (("verified", "true"),), "run gpu")
    publication = BenchmarkPublication(minimum, full, True, True)
    exit_report = Phase14ExitEvidence(True, True, True, True, True, True, True,
                                      "e" * 64, "f" * 64, True)
    operational_exit = Phase15ExitEvidence(True, True, True, True, True, True,
                                           842, 166, "1" * 64, "2" * 64, True)
    coverage = IntegrationCoverageManifest(
        NOW,
        IntegrationProgramStatus.INTEGRATION_INCOMPLETE,
        (
            IntegrationCoverageItem(
                "core",
                IntegrationMaturity.COMPONENT_TESTED,
                IntegrationMaturity.OPERATIONALLY_PROVEN,
                False,
                False,
                ("handoffs/0038-core-lifecycle-matrix.md",),
                ("Production gateway is not composed.",),
            ),
        ),
    )
    persisted_action = PersistedActionRecord(
        "action-1", "plan-1", "idempotency-1", action_proposal(),
        PersistedActionState.AWAITING_APPROVAL,
    )
    request_recovery = RequestRecoveryRecord(
        "request-1", RequestWorkKind.INFERENCE, RecoverableRequestState.ACTIVE,
    )
    worker_policy = WorkerBudgetPolicy("workers.full.v1", (
        WorkerBudgetShare(WorkerKind.MODEL, .85, .9, 1, 512),
        WorkerBudgetShare(WorkerKind.VERIFIER, .15, .8, .25, 128),
        WorkerBudgetShare(WorkerKind.CONNECTOR, .05, .8, .1, 64),
        WorkerBudgetShare(WorkerKind.TRAINING, .75, .9, .8, 512),
    ))
    runtime_model = RuntimeModelEntry(
        "qwen3:1.7b", "economical", (ModelIntent.CONVERSATION,),
        GIB, 8192, "a" * 64,
    )
    selection = RuntimeModelSelection(
        "selection-1", "request-1", ModelIntent.CONVERSATION,
        "qwen3:1.7b", "economical", GIB, 32 * GIB, 16 * GIB,
        ("capability.intent_match",),
    )
    execution = InferenceExecutionRecord(
        "instance-1", "request-1", ModelIntent.CONVERSATION, selection,
        InferenceExecutionState.TERMINAL, 2, "candidate-1",
        AssuranceLevel.UNVERIFIED,
    )
    capabilities = ("vscode.editor.active",)
    task = TaskRequest("application-request-1", "Observe editor", capabilities)
    permission = RequestPermissionContext(
        "local-owner", "shell-application-request-1",
        "authority-application-request-1", capabilities, NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest(
        "admission-application-request-1", task, permission, NOW,
    )
    route = RouteDecision(RouteName.CODE, 1.0, "Application task", capabilities)
    application_execution = ApplicationExecutionRecord(
        "application-instance-1", task.request_id,
        RoutedTaskRequest(admitted, RoutingResult(route)), "instance-1",
        "file:///workspace/main.py", "grant-1",
        ApplicationExecutionState.ACTIVE, 1, (observation_result(),),
    )
    return (review, update, release_manifest, recovery, soak, install, console, publication,
            exit_report, operational_exit, coverage, persisted_action,
            restart_decision(persisted_action), request_recovery,
            request_restart_decision(request_recovery), worker_policy,
            *derive_worker_limits(effective_budget(), worker_policy),
            runtime_model, selection, execution, application_execution)


def package_signature() -> PackageSignature:
    return PackageSignature(
        "key-1",
        SignatureAlgorithm.ED25519,
        base64.b64encode(b"s" * 64).decode("ascii"),
    )


def package_trust_policy() -> PackageTrustPolicy:
    return PackageTrustPolicy(
        "policy-1",
        ("Apache-2.0",),
        publisher_keys=(
            TrustedPublisherKey(
                "key-1",
                "publisher.fam",
                SignatureAlgorithm.ED25519,
                base64.b64encode(b"k" * 32).decode("ascii"),
            ),
        ),
        built_in_anchors=(
            BuiltInPackageAnchor(
                "package.builtin",
                "1.0.0",
                "publisher.fam",
                ArtifactDigest("sha256", "c" * 64),
            ),
        ),
    )


def package_validation_report() -> PackageValidationReport:
    return PackageValidationReport(
        "package.expert",
        "1.0.0",
        True,
        "accepted",
        PackageTrustLevel.SIGNED,
        ArtifactDigest("sha256", "a" * 64),
        "policy-1",
        "key-1",
    )


def expert_compatibility_report():
    return ExpertCompatibilityEvaluator().evaluate(
        expert_manifest(),
        host_inventory(),
        effective_budget(),
    )


def package_installation_state() -> ExpertPackageInstallationState:
    coordinate = ExpertPackageCoordinate("package.expert", "1.0.0")
    installed = InstalledExpertPackage(
        coordinate,
        "expert.code-small",
        "package.expert/1.0.0/artifact.bin",
        ArtifactDigest("sha256", "a" * 64),
        ArtifactDigest("sha256", "d" * 64),
        PackageTrustLevel.SIGNED,
        "policy-1",
        expert_compatibility_report().status,
        FULL_REFERENCE_WORKSTATION_PROFILE_ID,
        NOW,
        True,
    )
    event = PackageLifecycleEvent(
        "event-1",
        1,
        NOW,
        PackageLifecycleAction.INSTALL,
        coordinate,
        None,
        coordinate,
        "committed",
    )
    return ExpertPackageInstallationState(1, (installed,), (), (event,))


def expert_routing_embedding() -> ExpertRoutingEmbedding:
    return ExpertRoutingEmbedding(
        "embedding-code-python-v1",
        ExpertPackageCoordinate("package.expert", "1.0.0"),
        "expert.code-small",
        "publisher.fam",
        "embedding-space.test-v1",
        "expert.embedding-generator",
        "1.0.0",
        (0.6, 0.8),
        ("code.generate",),
        ArtifactDigest("sha256", "e" * 64),
        NOW,
        ("benchmark-run-1",),
    )


def expert_benchmark_run() -> ExpertBenchmarkRun:
    initial = ExpertBenchmarkAttempt(
        0,
        BenchmarkAttemptKind.INITIAL,
        "model.test:q4",
        VerifierContextDisclosure.NONE,
        None,
        False,
        ("stable_order.input_order",),
        1.0,
        100,
        40,
    )
    repaired = ExpertBenchmarkAttempt(
        1,
        BenchmarkAttemptKind.REPAIR,
        "model.test:q4",
        VerifierContextDisclosure.TRUSTED_TESTS_AND_EXAMPLES,
        ArtifactDigest("sha256", "f" * 64),
        True,
        (),
        1.2,
        200,
        50,
    )
    resources = ExpertBenchmarkResources(10, 20, 30, 40, 30, 50, 5)
    return ExpertBenchmarkRun(
        "benchmark-run-1",
        "stable-toposort",
        "2",
        ExpertPackageCoordinate("package.expert", "1.0.0"),
        "expert.code-small",
        FULL_REFERENCE_WORKSTATION_PROFILE_ID,
        "stable-toposort-v2",
        NOW,
        BenchmarkOutcome.VERIFIED_AFTER_REPAIR,
        ("stable_order", "neighbor_only", "cycle", "no_mutation"),
        (initial, repaired),
        resources,
        ArtifactDigest("sha256", "1" * 64),
    )


def expert_runtime_binding() -> ExpertRuntimeBinding:
    manifest = expert_manifest()
    return ExpertRuntimeBinding(
        ExpertPackageCoordinate("package.expert", "1.0.0"),
        manifest.expert_id,
        manifest.runtime_contract_id,
        "ollama.local/v1",
        "weights",
        "model.test:q4",
        manifest.package.artifact_digest,
    )


def resource_manifest_schema_values() -> tuple[object, ...]:
    return (
        host_inventory(),
        effective_budget(),
        legacy_expert_manifest(),
        expert_manifest(),
        verifier_manifest(),
        verifier_runtime_binding(),
        verifier_trust_policy(),
        verifier_activation_decision(),
        legacy_verification_declaration(),
        verification_declaration(),
        verification_run(),
        media_verification_report(),
        python_quality_report(),
        language_quality_report(),
        math_verification_request(),
        math_verification_report(),
        retrieval_verification_report(),
        *global_attempt_budget_values(),
        *mixed_benchmark_values(),
        *micro_expert_values(),
        escalation_trace(),
        *retrieval_tier_values(),
        *math_expert_values(),
        media_expert_evidence(),
        efficiency_report(),
        *evolution_values(),
        phase9_exit(),
        connector_manifest(),
        memory_record(),
        *memory_lifecycle_values(),
        *document_index_values(),
        *document_index_grant_values(),
        *memory_relevance_values(),
        memory_document_export(),
        *document_management_values(),
        memory_management_evidence(),
        memory_encryption_evidence(),
        memory_quality_report(),
        phase10_exit(),
        *outcome_prediction_values(),
        *preference_values(),
        *operating_policy_values(),
        *adaptation_drift_values(),
        phase11_exit(),
        verified_learning_outcome(),
        *live_adaptation_values(),
        *live_adaptation_control_values(),
        *device_identity_values(),
        *remote_privacy_values(),
        *remote_context_values(),
        *remote_execution_values(),
        *fabric_transport_values(),
        *expert_factory_values(),
        *product_values(),
        package_signature(),
        package_trust_policy(),
        package_validation_report(),
        expert_compatibility_report(),
        package_installation_state(),
        expert_routing_embedding(),
        expert_benchmark_run(),
        expert_runtime_binding(),
    )


def known_capability_schemas() -> frozenset[str]:
    return frozenset(
        {
            "capability.vscode.edit-input.v1",
            "capability.vscode.edit-output.v1",
            "evidence.document-hash.v1",
            "memory.document-chunk.v1",
        }
    )
