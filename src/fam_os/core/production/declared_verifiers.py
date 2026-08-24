"""Core-facing production service for activated declared verifier packages."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fam_os.core.production.verification import VerificationDecision
from fam_os.verification import VerificationRunRecord, VerificationStatus
from fam_os.verification.activation import DeclaredVerifierCatalog
from fam_os.verification.domain_adapters import ProductionVerifierAdapters


class ProductionDeclaredVerifier:
    def __init__(self, repositories, catalog: DeclaredVerifierCatalog, sandbox) -> None:
        self._repositories = repositories
        self._catalog = catalog
        self._adapters = ProductionVerifierAdapters(sandbox)

    def verify(self, _intent, request, candidate_id: str, candidate: str):
        declaration = self._repositories.verifications.declaration_for_request(
            request.request_id,
        )
        if declaration is None:
            return VerificationDecision(
                False, False, "", f"acceptance.{_intent.value}",
                "No typed deterministic verifier is declared for this request.",
            )
        activation_outcome = self._catalog.activate(declaration)
        activation = activation_outcome.activation
        if activation is None:
            return VerificationDecision(
                False, False, "", declaration.contract.acceptance_id,
                f"Declared verifier activation failed: {activation_outcome.reason_code}.",
            )
        verification_id = _verification_id(request.request_id, candidate_id)
        domain = self._adapters.verify(
            activation, declaration, candidate, verification_id,
        )
        runtime = activation.package
        report = runtime.package_report
        record = VerificationRunRecord(
            verification_id, request.request_id, candidate_id,
            declaration.declaration_id, runtime.manifest.verifier_id,
            declaration.contract.acceptance_id,
            runtime.manifest.package.package_id,
            runtime.manifest.package.package_version,
            runtime.binding.runtime_adapter_id,
            activation.verified_artifact_sha256,
            domain.status, domain.feedback, domain.facts,
            report.effective_trust.value if report.effective_trust is not None else "rejected",
            runtime.release_id, runtime.signer_key_id, datetime.now(timezone.utc),
        )
        if not self._repositories.verifications.add_run(record):
            existing = self._repositories.verifications.run(verification_id)
            if existing is None or (
                existing.request_id,
                existing.candidate_id,
                existing.declaration_id,
                existing.verifier_id,
                existing.verified_artifact_sha256,
            ) != (
                record.request_id,
                record.candidate_id,
                record.declaration_id,
                record.verifier_id,
                record.verified_artifact_sha256,
            ):
                raise RuntimeError("verification evidence identity was reused")
            record = existing
        available = domain.status is not VerificationStatus.ERROR
        return VerificationDecision(
            available, domain.status is VerificationStatus.PASSED,
            runtime.manifest.verifier_id, declaration.contract.acceptance_id,
            domain.feedback, record,
        )


def _verification_id(request_id: str, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{request_id}\0{candidate_id}".encode()).hexdigest()
    return f"verification-{digest}"
