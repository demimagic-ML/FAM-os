"""Expert identity, capability, and lifecycle contracts."""

from fam_os.experts.capabilities import (
    BUILT_IN_CAPABILITY_DOMAINS,
    EXPERT_CAPABILITY_NAMESPACE_VERSION,
    ExpertCapabilityId,
    capability_satisfies,
    parse_expert_capability_id,
    require_expert_capabilities,
)
from fam_os.experts.contracts import ExpertDescriptor, ExpertState, ExpertTier
from fam_os.experts.compatibility import ExpertCompatibilityEvaluator
from fam_os.experts.compatibility_contracts import (
    EXPERT_COMPATIBILITY_CONTRACT_VERSION,
    ExpertCompatibilityReport,
    ExpertCompatibilityStatus,
)
from fam_os.experts.legacy_manifest import (
    LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION,
    ExpertManifestV1Alpha1,
)
from fam_os.experts.manifest import (
    EXPERT_MANIFEST_CONTRACT_VERSION,
    ExpertManifest,
    ExpertResourceRequirements,
)
from fam_os.experts.migration import migrate_expert_manifest_v1alpha1
from fam_os.experts.ports import (
    ExpertBenchmarkSource,
    ExpertCatalog,
    ExpertManifestSource,
    ExpertRoutingEmbeddingSource,
)
from fam_os.experts.registry import LocalExpertRegistry
from fam_os.experts.registry_contracts import (
    ExpertPackageCoordinate,
    ExpertRegistryEvent,
    ExpertRegistrySnapshot,
    coordinate_for,
)
from fam_os.experts.routing_metadata import (
    EXPERT_ROUTING_METADATA_VERSION,
    ExpertRoutingEmbedding,
    ExpertRoutingMatch,
    RoutingEmbeddingQuery,
)
from fam_os.experts.routing_index import ExpertRoutingEmbeddingIndex
from fam_os.experts.benchmark_metadata import (
    EXPERT_BENCHMARK_METADATA_VERSION,
    BenchmarkAttemptKind,
    BenchmarkOutcome,
    ExpertBenchmarkAttempt,
    ExpertBenchmarkResources,
    ExpertBenchmarkRun,
    VerifierContextDisclosure,
    require_full_host_evidence,
)
from fam_os.experts.benchmark_index import ExpertBenchmarkIndex
from fam_os.experts.metadata_validation import (
    STABLE_TOPOSORT_REQUIREMENTS,
    require_stable_toposort_regression,
    require_successful_stable_toposort_regression,
    validate_routing_benchmark_links,
)
from fam_os.experts.runtime_binding import (
    EXPERT_RUNTIME_BINDING_VERSION,
    ExpertRuntimeBinding,
    validate_runtime_binding,
)
from fam_os.experts.installed_candidates import (
    InstalledExpertCandidate,
    InstalledExpertCandidateResolver,
)
from fam_os.experts.mixed_benchmark import (
    MIXED_BENCHMARK_CONTRACT_VERSION,
    BenchmarkTaskFamily,
    MixedBenchmarkCase,
    MixedBenchmarkCaseResult,
    MixedBenchmarkReport,
    MixedBenchmarkSuite,
    StrongRegressionRunRef,
    validate_mixed_report,
)

__all__ = [
    "BUILT_IN_CAPABILITY_DOMAINS",
    "BenchmarkAttemptKind",
    "BenchmarkOutcome",
    "EXPERT_CAPABILITY_NAMESPACE_VERSION",
    "EXPERT_COMPATIBILITY_CONTRACT_VERSION",
    "EXPERT_BENCHMARK_METADATA_VERSION",
    "EXPERT_MANIFEST_CONTRACT_VERSION",
    "EXPERT_ROUTING_METADATA_VERSION",
    "EXPERT_RUNTIME_BINDING_VERSION",
    "LEGACY_EXPERT_MANIFEST_CONTRACT_VERSION",
    "ExpertCatalog",
    "ExpertBenchmarkAttempt",
    "ExpertBenchmarkIndex",
    "ExpertBenchmarkResources",
    "ExpertBenchmarkRun",
    "ExpertBenchmarkSource",
    "ExpertCapabilityId",
    "ExpertCompatibilityEvaluator",
    "ExpertCompatibilityReport",
    "ExpertCompatibilityStatus",
    "ExpertDescriptor",
    "ExpertManifest",
    "ExpertManifestSource",
    "ExpertManifestV1Alpha1",
    "ExpertResourceRequirements",
    "ExpertPackageCoordinate",
    "ExpertRegistryEvent",
    "ExpertRegistrySnapshot",
    "ExpertRoutingEmbedding",
    "ExpertRoutingEmbeddingIndex",
    "ExpertRoutingMatch",
    "ExpertRuntimeBinding",
    "ExpertRoutingEmbeddingSource",
    "ExpertState",
    "ExpertTier",
    "LocalExpertRegistry",
    "InstalledExpertCandidate",
    "InstalledExpertCandidateResolver",
    "RoutingEmbeddingQuery",
    "STABLE_TOPOSORT_REQUIREMENTS",
    "VerifierContextDisclosure",
    "capability_satisfies",
    "coordinate_for",
    "migrate_expert_manifest_v1alpha1",
    "parse_expert_capability_id",
    "require_expert_capabilities",
    "require_full_host_evidence",
    "require_stable_toposort_regression",
    "require_successful_stable_toposort_regression",
    "validate_routing_benchmark_links",
    "validate_runtime_binding",
    "MIXED_BENCHMARK_CONTRACT_VERSION",
    "BenchmarkTaskFamily",
    "MixedBenchmarkCase",
    "MixedBenchmarkCaseResult",
    "MixedBenchmarkReport",
    "MixedBenchmarkSuite",
    "validate_mixed_report",
    "StrongRegressionRunRef",
]
