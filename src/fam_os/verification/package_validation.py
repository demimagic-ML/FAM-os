"""Digest, license, signature, and publisher trust validation for verifiers."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fam_os.registry.license_policy import require_allowed_license
from fam_os.registry.package import ArtifactDigest, PackageTrustLevel
from fam_os.registry.ports import PackageSignatureVerifier
from fam_os.registry.signing_payload import verifier_package_signing_payload
from fam_os.registry.trust_contracts import (
    PackageSignature,
    PackageTrustPolicy,
    PackageValidationReport,
    PublisherKeyStatus,
)
from fam_os.verification.manifest import VerifierManifest


@dataclass(frozen=True, slots=True)
class VerifierPackageValidationRequest:
    manifest: VerifierManifest
    observed_artifact_digest: ArtifactDigest
    signature: PackageSignature | None = None


@dataclass(slots=True)
class VerifierPackageValidator:
    policy: PackageTrustPolicy
    signature_verifier: PackageSignatureVerifier

    def validate(self, request: VerifierPackageValidationRequest) -> PackageValidationReport:
        reason = self._common_rejection(request)
        if reason:
            return self._report(request, False, reason)
        trust = request.manifest.package.trust_level
        if trust is PackageTrustLevel.BUILT_IN:
            return self._built_in(request)
        if trust is PackageTrustLevel.SIGNED:
            return self._signed(request)
        if request.signature is not None:
            return self._report(request, False, "signature.unexpected")
        if not self.policy.allow_local_unverified:
            return self._report(request, False, "trust.local_unverified_denied")
        return self._report(request, True, "accepted", PackageTrustLevel.LOCAL_UNVERIFIED)

    def _common_rejection(self, request) -> str | None:
        declared, observed = request.manifest.package.artifact_digest, request.observed_artifact_digest
        if declared.algorithm != "sha256" or observed.algorithm != "sha256":
            return "artifact.algorithm_unsupported"
        if not hmac.compare_digest(declared.value, observed.value):
            return "artifact.digest_mismatch"
        try:
            require_allowed_license(
                request.manifest.package.license_id,
                self.policy.allowed_license_expressions,
                allow_references=self.policy.allow_license_references,
            )
        except ValueError:
            return "license.invalid_expression"
        except PermissionError:
            return "license.denied"
        return None

    def _built_in(self, request) -> PackageValidationReport:
        package = request.manifest.package
        anchor = next((item for item in self.policy.built_in_anchors if (
            item.package_id, item.package_version
        ) == (package.package_id, package.package_version)), None)
        if anchor is None:
            return self._report(request, False, "trust.built_in_unanchored")
        if package.signature_key_id is not None or request.signature is not None:
            return self._report(request, False, "signature.unexpected")
        if anchor.publisher_id != package.publisher_id or anchor.artifact_digest != package.artifact_digest:
            return self._report(request, False, "trust.built_in_anchor_mismatch")
        return self._report(request, True, "accepted", PackageTrustLevel.BUILT_IN)

    def _signed(self, request) -> PackageValidationReport:
        package, signature = request.manifest.package, request.signature
        if signature is None:
            return self._report(request, False, "signature.missing")
        if signature.key_id != package.signature_key_id:
            return self._report(request, False, "signature.key_mismatch")
        key = next((item for item in self.policy.publisher_keys if item.key_id == signature.key_id), None)
        if key is None:
            return self._report(request, False, "signature.key_unknown")
        if key.status is PublisherKeyStatus.REVOKED:
            return self._report(request, False, "signature.key_revoked")
        if key.publisher_id != package.publisher_id or key.algorithm is not signature.algorithm:
            return self._report(request, False, "signature.publisher_or_algorithm_mismatch")
        try:
            valid = self.signature_verifier.verify(
                signature.algorithm, key.public_key_bytes(),
                verifier_package_signing_payload(request.manifest), signature.signature_bytes(),
            )
        except Exception:
            valid = False
        if not valid:
            return self._report(request, False, "signature.invalid")
        return self._report(request, True, "accepted", PackageTrustLevel.SIGNED, key.key_id)

    def _report(self, request, accepted, reason, trust=None, key_id=None):
        package = request.manifest.package
        return PackageValidationReport(
            package.package_id, package.package_version, accepted, reason, trust,
            request.observed_artifact_digest, self.policy.policy_id, key_id,
        )
