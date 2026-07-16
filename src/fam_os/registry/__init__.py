"""Signed package and compatibility registry."""

from fam_os.registry.package import ArtifactDigest, PackageMetadata, PackageTrustLevel
from fam_os.registry.license_policy import require_allowed_license, validate_spdx_expression
from fam_os.registry.ports import PackageSignatureVerifier
from fam_os.registry.trust_contracts import (
    REGISTRY_TRUST_CONTRACT_VERSION,
    BuiltInPackageAnchor,
    PackageSignature,
    PackageTrustPolicy,
    PackageValidationReport,
    PublisherKeyStatus,
    SignatureAlgorithm,
    TrustedPublisherKey,
)
__all__ = [
    "REGISTRY_TRUST_CONTRACT_VERSION",
    "ArtifactDigest",
    "BuiltInPackageAnchor",
    "PackageMetadata",
    "PackageSignature",
    "PackageSignatureVerifier",
    "PackageTrustLevel",
    "PackageTrustPolicy",
    "PackageValidationReport",
    "PublisherKeyStatus",
    "SignatureAlgorithm",
    "TrustedPublisherKey",
    "require_allowed_license",
    "validate_spdx_expression",
]
