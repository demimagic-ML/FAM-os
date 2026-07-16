"""Representative hardware and component manifest schema values."""

from datetime import timedelta

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
)
from fam_os.fabric import (
    DeviceEnrollmentChallenge, DeviceEnrollmentRecord, DeviceEnrollmentRequest,
    DeviceIdentity,
    RemoteContextRequest, RemoteContextSensitivity, RemoteExpertCapability,
    RemotePrivacyDecision, RemotePrivacyPolicy,
    FabricEncryptedEnvelope, FabricHandshake, FabricRecoveryDecision,
    FabricRouteCandidate, FabricRouteDecision, RemoteFailureKind,
    MultiDeviceDemoReport,
)
from fam_os.expert_factory import (
    AdapterTrainingPlan, DistillationPlan, EvaluationPlan, FactoryLifecycleReport,
    FailureTrace, FailureTraceCluster, HardwareTrainingMetrics, MissingCapabilityProposal,
    PublishedExpertPackage, QuantizedVariant, RegressionGateResult, TeacherDataset,
    train_micro_expert, LabeledExample,
)
from fam_os.console.contracts import ConsoleItem, ConsoleSection, ConsoleSnapshot
from fam_os.product.benchmark_publication import (
    BenchmarkPublication, ProfileBenchmarkSummary,
)
from fam_os.product.linux_installation import InstallationReceipt
from fam_os.product.phase14_exit import Phase14ExitEvidence
from fam_os.product.phase15_exit import Phase15ExitEvidence
from fam_os.product.recovery_mode import RecoveryDecision, RecoveryOperation
from fam_os.product.soak_contracts import SoakReport
from fam_os.product.update_contracts import UpdateReceipt
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
    VerifierActivationDecision,
    VerifierManifest,
    VerifierRuntimeBinding,
    VerifierTrustPolicy,
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
from tests.contract.schema_application_fixtures import NOW, capability


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
        "trusted answer", (RetrievalClaim("claim-1", ("citation-1",)),),
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
        "d" * 64, ("source-1",), ("claim-1",), "trusted answer", True,
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


def memory_relevance_values():
    candidate = MemoryRetrievalCandidate(
        "memory-1", MemoryScope("user-1", ("assist",)), NOW, .8, 20,
    )
    decision = MemoryRelevanceDecision(
        ("memory-1",), 20, (MemoryRejection("memory-2", "memory.stale"),),
    )
    return candidate, decision


def memory_document_export():
    approval = document_index_values()[0]
    import hashlib
    return MemoryDocumentExport(approval, "content", hashlib.sha256(b"content").hexdigest())


def memory_management_evidence():
    return MemoryManagementEvidence("management", True, True, True, True, 0, True)


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


def device_identity_values():
    raw = b"k" * 32
    identity = DeviceIdentity("device", "Device", base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest())
    request = DeviceEnrollmentRequest("request", identity, NOW)
    challenge = DeviceEnrollmentChallenge("request", base64.b64encode(b"n" * 32).decode(), NOW + timedelta(minutes=1))
    record = DeviceEnrollmentRecord(identity, NOW, "owner", True)
    return identity, request, challenge, record


def remote_privacy_values():
    capability = RemoteExpertCapability("device", "expert", ("code.generate",), 1000, "a" * 64)
    policy = RemotePrivacyPolicy("owner", ("device",), ("assist",), ("workspace",),
                                 1000, (RemoteContextSensitivity.PRIVATE,), False)
    request = RemoteContextRequest("owner", "device", "assist", "workspace",
                                   RemoteContextSensitivity.PRIVATE, 100, False)
    return capability, policy, request, RemotePrivacyDecision(True, ())


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
    return trace, cluster, missing, dataset, distill, adapter, evaluation, trained, metrics, variant, published, gate, lifecycle


def product_values():
    review = SecurityReviewReport("review", False, ("bandit",), (("bandit.json", "a" * 64),),
                                  (FindingDisposition("B1", "low", "accepted", "bounded"),), (), True)
    update = UpdateReceipt("v2", "v1", True, True, True, False, "v2", "activated")
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
    return (review, update, recovery, soak, install, console, publication,
            exit_report, operational_exit)


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
        *memory_relevance_values(),
        memory_document_export(),
        memory_management_evidence(),
        memory_encryption_evidence(),
        memory_quality_report(),
        phase10_exit(),
        *outcome_prediction_values(),
        *preference_values(),
        *operating_policy_values(),
        *adaptation_drift_values(),
        phase11_exit(),
        *device_identity_values(),
        *remote_privacy_values(),
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
