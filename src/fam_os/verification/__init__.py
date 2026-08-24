"""Deterministic verification contracts and sandbox boundary."""

from fam_os.verification.contracts import (
    VerificationEvidence,
    VerificationReport,
    VerificationRequest,
    VerificationStatus,
)
from fam_os.verification.ports import Verifier
from fam_os.verification.manifest import (
    VERIFIER_MANIFEST_CONTRACT_VERSION,
    DeterminismClass,
    VerifierManifest,
)
from fam_os.verification.sandbox import (
    IsolationLevel,
    SandboxLimits,
    SandboxRequest,
    SandboxResult,
    SandboxRunner,
    SandboxStatus,
)
from fam_os.verification.runtime_binding import (
    VERIFIER_RUNTIME_BINDING_VERSION,
    VerifierRuntimeBinding,
    validate_verifier_runtime_binding,
)
from fam_os.verification.trust import (
    VERIFIER_ACTIVATION_DECISION_VERSION,
    VERIFIER_TRUST_POLICY_VERSION,
    VerifierActivationDecision,
    VerifierActivationRequest,
    VerifierTrustEvaluator,
    VerifierTrustPolicy,
)
from fam_os.verification.package_validation import (
    VerifierPackageValidationRequest,
    VerifierPackageValidator,
)
from fam_os.verification.language_quality import (
    LANGUAGE_QUALITY_CONTRACT_VERSION,
    LanguageGateEvidence,
    LanguageGateStatus,
    LanguageQualityReport,
)
from fam_os.verification.math_contracts import (
    MATH_VERIFICATION_CONTRACT_VERSION,
    MathVerificationReport,
    MathVerificationRequest,
)
from fam_os.verification.retrieval import (
    RETRIEVAL_VERIFICATION_CONTRACT_VERSION,
    RetrievalCitation,
    RetrievalCitationVerifier,
    RetrievalClaim,
    RetrievalQueryObligation,
    RetrievalVerificationReport,
    RetrievedSource,
    missing_retrieval_terms,
    retrieval_query_obligation,
    retrieval_terms,
)
from fam_os.verification.application_actions import ActivatedApplicationConditionVerifier
from fam_os.verification.declarations import (
    VERIFICATION_DECLARATION_VERSION,
    VERIFICATION_RUN_VERSION,
    ExactTextVerification,
    MathEquivalenceVerification,
    MediaArtifactTextVerification,
    MediaModality,
    PythonTestsVerification,
    RetrievalCitationsVerification,
    VerificationDeclaration,
    VerificationFact,
    VerificationKind,
    VerificationRunRecord,
    VerificationSpecification,
    VerifierContractReference,
    contract_for_kind,
)
from fam_os.verification.legacy_declarations import (
    LEGACY_VERIFICATION_DECLARATION_VERSION,
    VerificationDeclaration as VerificationDeclarationV1Alpha1,
    migrate_verification_declaration_v1alpha1,
)
from fam_os.verification.media import (
    MEDIA_VERIFICATION_VERSION,
    MediaArtifactTextReport,
    MediaArtifactTextVerifier,
    read_verified_media,
)
from fam_os.verification.retrieval_candidate import (
    ParsedRetrievalCandidate,
    ParsedRetrievalClaim,
    parse_retrieval_candidate,
)

__all__ = [
    "IsolationLevel",
    "SandboxLimits",
    "SandboxRequest",
    "SandboxResult",
    "SandboxRunner",
    "SandboxStatus",
    "VerificationEvidence",
    "VERIFIER_MANIFEST_CONTRACT_VERSION",
    "DeterminismClass",
    "VerificationReport",
    "VerificationRequest",
    "VerificationStatus",
    "Verifier",
    "VerifierManifest",
    "VERIFIER_RUNTIME_BINDING_VERSION",
    "VERIFIER_ACTIVATION_DECISION_VERSION",
    "VERIFIER_TRUST_POLICY_VERSION",
    "VerifierRuntimeBinding",
    "validate_verifier_runtime_binding",
    "VerifierActivationDecision",
    "VerifierActivationRequest",
    "VerifierTrustEvaluator",
    "VerifierTrustPolicy",
    "VerifierPackageValidationRequest",
    "VerifierPackageValidator",
    "LANGUAGE_QUALITY_CONTRACT_VERSION",
    "LanguageGateEvidence",
    "LanguageGateStatus",
    "LanguageQualityReport",
    "MATH_VERIFICATION_CONTRACT_VERSION",
    "MathVerificationReport",
    "MathVerificationRequest",
    "RETRIEVAL_VERIFICATION_CONTRACT_VERSION",
    "RetrievalCitation",
    "RetrievalCitationVerifier",
    "RetrievalClaim",
    "RetrievalQueryObligation",
    "RetrievalVerificationReport",
    "RetrievedSource",
    "missing_retrieval_terms",
    "retrieval_query_obligation",
    "retrieval_terms",
    "ActivatedApplicationConditionVerifier",
    "VERIFICATION_DECLARATION_VERSION",
    "VERIFICATION_RUN_VERSION",
    "ExactTextVerification",
    "MathEquivalenceVerification",
    "MediaArtifactTextVerification",
    "MediaModality",
    "PythonTestsVerification",
    "RetrievalCitationsVerification",
    "VerificationDeclaration",
    "VerificationFact",
    "VerificationKind",
    "VerificationRunRecord",
    "VerificationSpecification",
    "VerifierContractReference",
    "contract_for_kind",
    "LEGACY_VERIFICATION_DECLARATION_VERSION",
    "VerificationDeclarationV1Alpha1",
    "migrate_verification_declaration_v1alpha1",
    "MEDIA_VERIFICATION_VERSION",
    "MediaArtifactTextReport",
    "MediaArtifactTextVerifier",
    "read_verified_media",
    "ParsedRetrievalCandidate",
    "ParsedRetrievalClaim",
    "parse_retrieval_candidate",
]
