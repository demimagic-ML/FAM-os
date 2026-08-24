"""Fail-closed selection of an exact declared verifier runtime package."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.registry import PackageTrustLevel
from fam_os.registry.trust_contracts import PackageValidationReport
from fam_os.verification.declarations import VerificationDeclaration
from fam_os.verification.manifest import VerifierManifest
from fam_os.verification.runtime_binding import VerifierRuntimeBinding
from fam_os.verification.trust import (
    VerifierActivationRequest,
    VerifierTrustEvaluator,
    VerifierTrustPolicy,
)


@dataclass(frozen=True, slots=True)
class VerifierRuntimePackage:
    manifest: VerifierManifest
    binding: VerifierRuntimeBinding
    package_report: PackageValidationReport
    release_id: str | None = None
    signer_key_id: str | None = None

    def __post_init__(self) -> None:
        if (self.release_id is None) != (self.signer_key_id is None):
            raise ValueError("verifier release and signer evidence must be paired")
        if self.package_report.effective_trust is PackageTrustLevel.SIGNED:
            if self.signer_key_id != self.package_report.verified_key_id:
                raise ValueError("verifier package signer evidence does not match")


@dataclass(frozen=True, slots=True)
class ActivatedVerifier:
    package: VerifierRuntimePackage
    verified_artifact_sha256: str


@dataclass(frozen=True, slots=True)
class VerifierActivationOutcome:
    activation: ActivatedVerifier | None
    reason_code: str


class DeclaredVerifierCatalog:
    def __init__(
        self,
        packages: tuple[VerifierRuntimePackage, ...],
        minimum_trust: PackageTrustLevel,
        available_isolation_capabilities: tuple[str, ...],
    ) -> None:
        identities = tuple(item.manifest.verifier_id for item in packages)
        if len(set(identities)) != len(identities):
            raise ValueError("declared verifier IDs must be unique")
        if not available_isolation_capabilities:
            raise ValueError("verifier catalog requires observed isolation capabilities")
        self._packages = {item.manifest.verifier_id: item for item in packages}
        self._isolation = available_isolation_capabilities
        self._evaluator = VerifierTrustEvaluator(VerifierTrustPolicy(
            "production-verifier-activation",
            identities,
            tuple(dict.fromkeys(item.manifest.runner_contract_id for item in packages)),
            minimum_trust,
        ))

    def activate(self, declaration: VerificationDeclaration) -> VerifierActivationOutcome:
        runtime = self._packages.get(declaration.contract.verifier_id)
        if runtime is None:
            return VerifierActivationOutcome(None, "runtime.verifier_not_declared")
        request = VerifierActivationRequest(
            runtime.manifest, runtime.binding, runtime.package_report,
            declaration.contract.acceptance_id,
            declaration.contract.candidate_schema_id,
            declaration.contract.evidence_schema_id,
            self._isolation,
        )
        decision = self._evaluator.evaluate(request)
        if not decision.allowed or decision.verified_artifact_digest is None:
            return VerifierActivationOutcome(None, decision.reason_code)
        return VerifierActivationOutcome(
            ActivatedVerifier(runtime, decision.verified_artifact_digest),
            decision.reason_code,
        )

    def verifier_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._packages))
