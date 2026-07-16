"""Pure expert package digest, license, signature, and trust validation."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fam_os.experts.manifest import ExpertManifest
from fam_os.registry.license_policy import require_allowed_license
from fam_os.registry.package import ArtifactDigest, PackageTrustLevel
from fam_os.registry.ports import PackageSignatureVerifier
from fam_os.registry.signing_payload import expert_package_signing_payload
from fam_os.registry.trust_contracts import (
    BuiltInPackageAnchor,
    PackageSignature,
    PackageTrustPolicy,
    PackageValidationReport,
    PublisherKeyStatus,
)


@dataclass(frozen=True, slots=True)
class PackageValidationRequest:
    manifest: ExpertManifest
    observed_artifact_digest: ArtifactDigest
    signature: PackageSignature | None = None


@dataclass(slots=True)
class ExpertPackageValidator:
    policy: PackageTrustPolicy
    signature_verifier: PackageSignatureVerifier

    def validate(self, request: PackageValidationRequest) -> PackageValidationReport:
        package = request.manifest.package
        reason = self._integrity_and_license_reason(request)
        if reason is not None:
            return self._rejected(request, reason)
        if package.trust_level is PackageTrustLevel.BUILT_IN:
            return self._validate_built_in(request)
        if package.trust_level is PackageTrustLevel.SIGNED:
            return self._validate_signed(request)
        if request.signature is not None:
            return self._rejected(request, "signature.unexpected")
        if not self.policy.allow_local_unverified:
            return self._rejected(request, "trust.local_unverified_denied")
        return self._accepted(request, PackageTrustLevel.LOCAL_UNVERIFIED)

    def _integrity_and_license_reason(self, request: PackageValidationRequest) -> str | None:
        declared = request.manifest.package.artifact_digest
        observed = request.observed_artifact_digest
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

    def _validate_built_in(self, request: PackageValidationRequest) -> PackageValidationReport:
        package = request.manifest.package
        anchor = _find_anchor(self.policy.built_in_anchors, package.package_id, package.package_version)
        if anchor is None:
            return self._rejected(request, "trust.built_in_unanchored")
        if package.signature_key_id is not None:
            return self._rejected(request, "trust.built_in_key_claim")
        if anchor.publisher_id != package.publisher_id or anchor.artifact_digest != package.artifact_digest:
            return self._rejected(request, "trust.built_in_anchor_mismatch")
        if request.signature is not None:
            return self._rejected(request, "signature.unexpected")
        return self._accepted(request, PackageTrustLevel.BUILT_IN)

    def _validate_signed(self, request: PackageValidationRequest) -> PackageValidationReport:
        package = request.manifest.package
        signature = request.signature
        if signature is None:
            return self._rejected(request, "signature.missing")
        if signature.key_id != package.signature_key_id:
            return self._rejected(request, "signature.key_mismatch")
        key = next((item for item in self.policy.publisher_keys if item.key_id == signature.key_id), None)
        if key is None:
            return self._rejected(request, "signature.key_unknown")
        if key.status is PublisherKeyStatus.REVOKED:
            return self._rejected(request, "signature.key_revoked")
        if key.publisher_id != package.publisher_id or key.algorithm is not signature.algorithm:
            return self._rejected(request, "signature.publisher_or_algorithm_mismatch")
        try:
            valid = self.signature_verifier.verify(
                signature.algorithm,
                key.public_key_bytes(),
                expert_package_signing_payload(request.manifest),
                signature.signature_bytes(),
            )
        except Exception:
            return self._rejected(request, "signature.verifier_failed")
        if not valid:
            return self._rejected(request, "signature.invalid")
        return self._accepted(request, PackageTrustLevel.SIGNED, key.key_id)

    def _accepted(
        self,
        request: PackageValidationRequest,
        trust: PackageTrustLevel,
        key_id: str | None = None,
    ) -> PackageValidationReport:
        return _report(request, self.policy.policy_id, True, "accepted", trust, key_id)

    def _rejected(self, request: PackageValidationRequest, reason: str) -> PackageValidationReport:
        return _report(request, self.policy.policy_id, False, reason, None, None)


def _find_anchor(anchors, package_id, package_version) -> BuiltInPackageAnchor | None:
    return next(
        (
            item
            for item in anchors
            if item.package_id == package_id and item.package_version == package_version
        ),
        None,
    )


def _report(request, policy_id, accepted, reason, trust, key_id) -> PackageValidationReport:
    package = request.manifest.package
    return PackageValidationReport(
        package.package_id,
        package.package_version,
        accepted,
        reason,
        trust,
        request.observed_artifact_digest,
        policy_id,
        key_id,
    )
