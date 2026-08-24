"""Frozen v1alpha1 verifier declarations and fail-closed migration."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from fam_os.verification.declarations import (
    ExactTextVerification,
    MathEquivalenceVerification,
    MediaArtifactTextVerification,
    PythonTestsVerification,
    RetrievalCitationsVerification as CurrentRetrievalCitationsVerification,
    VerificationDeclaration as CurrentVerificationDeclaration,
    VerificationKind,
    VerifierContractReference,
    contract_for_kind,
)
from fam_os.verification.retrieval import RetrievedSource


LEGACY_VERIFICATION_DECLARATION_VERSION = "fam.verifier.declaration/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


@dataclass(frozen=True, slots=True)
class RetrievalCitationsVerification:
    """Exact historical retrieval declaration shape without a query binding."""

    sources: tuple[RetrievedSource, ...]
    kind: VerificationKind = VerificationKind.RETRIEVAL_CITATIONS

    def __post_init__(self) -> None:
        if not self.sources or len(self.sources) > 32:
            raise ValueError("legacy retrieval verification requires 1-32 sources")
        identities = tuple(item.source_id for item in self.sources)
        if len(set(identities)) != len(identities):
            raise ValueError("legacy retrieval source IDs must be unique")
        if sum(len(item.content) for item in self.sources) > 262_144:
            raise ValueError("legacy retrieval source content exceeds its bound")
        if any(
            _content_sha256(item.content) != item.content_sha256
            for item in self.sources
        ):
            raise ValueError("legacy retrieval source digest does not match its bytes")
        if self.kind is not VerificationKind.RETRIEVAL_CITATIONS:
            raise ValueError("legacy retrieval verification kind is invalid")


VerificationSpecification = (
    ExactTextVerification
    | PythonTestsVerification
    | RetrievalCitationsVerification
    | MathEquivalenceVerification
    | MediaArtifactTextVerification
)


@dataclass(frozen=True, slots=True)
class VerificationDeclaration:
    declaration_id: str
    request_id: str
    contract: VerifierContractReference
    specification: VerificationSpecification
    contract_version: str = LEGACY_VERIFICATION_DECLARATION_VERSION

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.declaration_id):
            raise ValueError("legacy verification declaration identity is invalid")
        if not _IDENTIFIER.fullmatch(self.request_id):
            raise ValueError("legacy verification request identity is invalid")
        if self.contract_version != LEGACY_VERIFICATION_DECLARATION_VERSION:
            raise ValueError("unsupported legacy verification declaration version")
        if self.contract != contract_for_kind(self.specification.kind):
            raise ValueError("legacy verification declaration contract is invalid")


def migrate_verification_declaration_v1alpha1(
    value: VerificationDeclaration,
) -> CurrentVerificationDeclaration:
    """Migrate structure while leaving legacy retrieval permanently unbound."""

    specification = value.specification
    if isinstance(specification, RetrievalCitationsVerification):
        current = CurrentRetrievalCitationsVerification(specification.sources, None)
    else:
        current = specification
    return CurrentVerificationDeclaration(
        value.declaration_id,
        value.request_id,
        contract_for_kind(current.kind),
        current,
    )

def _content_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
