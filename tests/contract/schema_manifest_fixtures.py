"""Representative hardware and component manifest schema values."""

from datetime import UTC, datetime, timedelta

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
)
from fam_os.memory import (
    MemoryContentDigest,
    MemoryProvenance,
    MemoryRecordKind,
    MemoryRecordManifest,
    MemoryScope,
    MemorySensitivity,
    MemorySourceKind,
)
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
from fam_os.verification.retrieval import RetrievalVerificationReport
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
        connector_manifest(),
        memory_record(),
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
