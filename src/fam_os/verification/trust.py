"""Fail-closed trust decision for activating verifier runtimes."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.registry import PackageTrustLevel
from fam_os.registry.trust_contracts import PackageValidationReport
from fam_os.verification.manifest import VerifierManifest
from fam_os.verification.runtime_binding import (
    VerifierRuntimeBinding,
    validate_verifier_runtime_binding,
)


VERIFIER_TRUST_POLICY_VERSION = "fam.verifier.trust-policy/v1alpha1"
VERIFIER_ACTIVATION_DECISION_VERSION = "fam.verifier.activation-decision/v1alpha1"


@dataclass(frozen=True, slots=True)
class VerifierTrustPolicy:
    policy_id: str
    allowed_verifier_ids: tuple[str, ...]
    allowed_runner_contract_ids: tuple[str, ...]
    minimum_trust: PackageTrustLevel
    require_network_denied: bool = True
    contract_version: str = VERIFIER_TRUST_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != VERIFIER_TRUST_POLICY_VERSION:
            raise ValueError("unsupported verifier trust policy contract_version")
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")
        for name in ("allowed_verifier_ids", "allowed_runner_contract_ids"):
            values = getattr(self, name)
            if not values or any(not value.strip() for value in values):
                raise ValueError(f"{name} requires non-empty values")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} values must be unique")


@dataclass(frozen=True, slots=True)
class VerifierActivationRequest:
    manifest: VerifierManifest
    binding: VerifierRuntimeBinding
    package_report: PackageValidationReport
    acceptance_id: str
    candidate_schema_id: str
    evidence_schema_id: str
    available_isolation_capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerifierActivationDecision:
    allowed: bool
    reason_code: str
    verifier_id: str
    package_id: str
    package_version: str
    policy_id: str
    verified_artifact_digest: str | None
    contract_version: str = VERIFIER_ACTIVATION_DECISION_VERSION


@dataclass(frozen=True, slots=True)
class VerifierTrustEvaluator:
    policy: VerifierTrustPolicy

    def evaluate(self, request: VerifierActivationRequest) -> VerifierActivationDecision:
        reason = self._rejection_reason(request)
        return self._decision(request, reason is None, reason or "accepted")

    def _rejection_reason(self, request: VerifierActivationRequest) -> str | None:
        manifest, report = request.manifest, request.package_report
        try:
            validate_verifier_runtime_binding(manifest, request.binding)
        except ValueError:
            return "runtime.binding_mismatch"
        package = manifest.package
        if not report.accepted or report.effective_trust is None:
            return "package.validation_rejected"
        if (report.package_id, report.package_version) != (package.package_id, package.package_version):
            return "package.identity_mismatch"
        if report.observed_artifact_digest != package.artifact_digest:
            return "package.observed_digest_mismatch"
        if _trust_rank(report.effective_trust) < _trust_rank(self.policy.minimum_trust):
            return "package.trust_below_minimum"
        if manifest.verifier_id not in self.policy.allowed_verifier_ids:
            return "authority.verifier_denied"
        if manifest.runner_contract_id not in self.policy.allowed_runner_contract_ids:
            return "authority.runner_denied"
        if request.acceptance_id not in manifest.acceptance_ids:
            return "authority.acceptance_undeclared"
        if request.candidate_schema_id not in manifest.candidate_schema_ids:
            return "authority.candidate_schema_undeclared"
        if request.evidence_schema_id != manifest.evidence_schema_id:
            return "authority.evidence_schema_mismatch"
        available = set(request.available_isolation_capabilities)
        if not set(manifest.required_isolation_capabilities).issubset(available):
            return "isolation.capability_missing"
        if self.policy.require_network_denied and (
            manifest.network_access or "isolation.network-denied" not in available
        ):
            return "isolation.network_denial_required"
        return None

    def _decision(self, request, allowed, reason) -> VerifierActivationDecision:
        report, package = request.package_report, request.manifest.package
        digest = report.observed_artifact_digest.value if allowed else None
        return VerifierActivationDecision(
            allowed, reason, request.manifest.verifier_id, package.package_id,
            package.package_version, self.policy.policy_id, digest,
        )


def _trust_rank(level: PackageTrustLevel) -> int:
    return {
        PackageTrustLevel.LOCAL_UNVERIFIED: 0,
        PackageTrustLevel.SIGNED: 1,
        PackageTrustLevel.BUILT_IN: 2,
    }[level]
