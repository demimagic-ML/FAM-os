"""Direct canary use of the activated production verifier package boundary."""

from __future__ import annotations

import hashlib

from fam_os.verification import VerificationStatus
from fam_os.verification.activation import DeclaredVerifierCatalog
from fam_os.verification.declarations import (
    PythonTestsVerification,
    VerificationDeclaration,
    contract_for_kind,
)
from fam_os.verification.domain_adapters import ProductionVerifierAdapters
from fam_os.verification.sandbox import SandboxRunner


class DeclaredCanaryVerifier:
    def __init__(
        self, catalog: DeclaredVerifierCatalog, sandbox: SandboxRunner,
    ) -> None:
        self._catalog = catalog
        self._adapters = ProductionVerifierAdapters(sandbox)

    def verify(
        self, *, verifier_id: str, case_id: str, candidate: str,
        bundle_id: str, test_source: str,
    ) -> bool:
        specification = PythonTestsVerification(
            bundle_id, test_source,
            hashlib.sha256(test_source.encode()).hexdigest(),
        )
        contract = contract_for_kind(specification.kind)
        if contract.verifier_id != verifier_id:
            return False
        declaration = VerificationDeclaration(
            f"canary-declaration-{case_id}", f"canary-request-{case_id}",
            contract, specification,
        )
        activation = self._catalog.activate(declaration).activation
        if activation is None or activation.package.manifest.verifier_id != verifier_id:
            return False
        result = self._adapters.verify(
            activation, declaration, candidate, f"canary-verification-{case_id}",
        )
        return result.status is VerificationStatus.PASSED
