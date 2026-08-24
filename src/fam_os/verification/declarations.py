"""Typed acceptance declarations and durable production verifier evidence."""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from fam_os.verification.contracts import VerificationStatus
from fam_os.verification.retrieval import (
    RetrievalQueryObligation,
    RetrievedSource,
    missing_retrieval_terms,
)


VERIFICATION_DECLARATION_VERSION = "fam.verifier.declaration/v1alpha2"
VERIFICATION_RUN_VERSION = "fam.verifier.run/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


class VerificationKind(StrEnum):
    EXACT_TEXT = "exact_text"
    PYTHON_TESTS = "python_tests"
    RETRIEVAL_CITATIONS = "retrieval_citations"
    MATH_EQUIVALENCE = "math_equivalence"
    MEDIA_ARTIFACT_TEXT = "media_artifact_text"


class MediaModality(StrEnum):
    IMAGE_OCR = "image_ocr"


@dataclass(frozen=True, slots=True)
class VerifierContractReference:
    verifier_id: str
    acceptance_id: str
    candidate_schema_id: str
    evidence_schema_id: str

    def __post_init__(self) -> None:
        for name in (
            "verifier_id", "acceptance_id", "candidate_schema_id",
            "evidence_schema_id",
        ):
            _identifier(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class ExactTextVerification:
    expected_text: str
    kind: VerificationKind = VerificationKind.EXACT_TEXT

    def __post_init__(self) -> None:
        _bounded_text(self.expected_text, "expected_text", 16_000)
        if self.kind is not VerificationKind.EXACT_TEXT:
            raise ValueError("exact-text verification kind is invalid")


@dataclass(frozen=True, slots=True)
class PythonTestsVerification:
    bundle_id: str
    test_source: str
    test_source_sha256: str
    kind: VerificationKind = VerificationKind.PYTHON_TESTS

    def __post_init__(self) -> None:
        _identifier(self.bundle_id, "bundle_id")
        _bounded_text(self.test_source, "test_source", 131_072)
        _sha256(self.test_source_sha256, "test_source_sha256")
        if _content_sha256(self.test_source) != self.test_source_sha256:
            raise ValueError("Python test source digest does not match its bytes")
        ast.parse(self.test_source)
        if self.kind is not VerificationKind.PYTHON_TESTS:
            raise ValueError("Python-test verification kind is invalid")


@dataclass(frozen=True, slots=True)
class RetrievalCitationsVerification:
    sources: tuple[RetrievedSource, ...]
    query: RetrievalQueryObligation | None = None
    kind: VerificationKind = VerificationKind.RETRIEVAL_CITATIONS

    def __post_init__(self) -> None:
        if not self.sources or len(self.sources) > 32:
            raise ValueError("retrieval verification requires 1-32 sources")
        identities = tuple(item.source_id for item in self.sources)
        if len(set(identities)) != len(identities):
            raise ValueError("retrieval source IDs must be unique")
        if sum(len(item.content) for item in self.sources) > 262_144:
            raise ValueError("retrieval source content exceeds its bound")
        if any(_content_sha256(item.content) != item.content_sha256 for item in self.sources):
            raise ValueError("retrieval source digest does not match its bytes")
        if self.query is not None and missing_retrieval_terms(
            tuple(item.content for item in self.sources), self.query,
        ):
            raise ValueError("retrieval sources do not cover every required query term")
        if self.kind is not VerificationKind.RETRIEVAL_CITATIONS:
            raise ValueError("retrieval verification kind is invalid")


@dataclass(frozen=True, slots=True)
class MathEquivalenceVerification:
    reference_expression: str
    variable: str
    sample_points: tuple[str, ...]
    absolute_tolerance: str
    precision_digits: int = 50
    kind: VerificationKind = VerificationKind.MATH_EQUIVALENCE

    def __post_init__(self) -> None:
        for name in ("reference_expression", "variable", "absolute_tolerance"):
            _bounded_text(getattr(self, name), name, 8_192)
        if not self.sample_points or len(self.sample_points) > 256:
            raise ValueError("math verification requires 1-256 sample points")
        if any(
            not value.strip() or "\x00" in value or len(value) > 256
            for value in self.sample_points
        ):
            raise ValueError("math sample points must be bounded nonempty text")
        if self.precision_digits < 16 or self.precision_digits > 1_000:
            raise ValueError("math precision must be between 16 and 1000 digits")
        if self.kind is not VerificationKind.MATH_EQUIVALENCE:
            raise ValueError("math verification kind is invalid")


@dataclass(frozen=True, slots=True)
class MediaArtifactTextVerification:
    artifact_path: str
    artifact_sha256: str
    expected_text: str
    maximum_artifact_bytes: int = 20 * 1024 * 1024
    modality: MediaModality = MediaModality.IMAGE_OCR
    kind: VerificationKind = VerificationKind.MEDIA_ARTIFACT_TEXT

    def __post_init__(self) -> None:
        _bounded_text(self.artifact_path, "artifact_path", 4_096)
        if not Path(self.artifact_path).is_absolute():
            raise ValueError("media artifact path must be absolute")
        _sha256(self.artifact_sha256, "artifact_sha256")
        _bounded_text(self.expected_text, "expected_text", 16_000)
        if self.maximum_artifact_bytes < 1 or self.maximum_artifact_bytes > 100 * 1024 * 1024:
            raise ValueError("media artifact byte limit is invalid")
        if self.modality is not MediaModality.IMAGE_OCR:
            raise ValueError("unsupported media verification modality")
        if self.kind is not VerificationKind.MEDIA_ARTIFACT_TEXT:
            raise ValueError("media verification kind is invalid")


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
    contract_version: str = VERIFICATION_DECLARATION_VERSION

    def __post_init__(self) -> None:
        _identifier(self.declaration_id, "declaration_id")
        _identifier(self.request_id, "request_id")
        if self.contract_version != VERIFICATION_DECLARATION_VERSION:
            raise ValueError("unsupported verification declaration version")
        if self.contract != contract_for_kind(self.specification.kind):
            raise ValueError("verification declaration contract does not match its kind")


@dataclass(frozen=True, slots=True)
class VerificationFact:
    name: str
    value: str

    def __post_init__(self) -> None:
        _identifier(self.name, "verification fact name")
        _bounded_text(self.value, "verification fact value", 16_000)


@dataclass(frozen=True, slots=True)
class VerificationRunRecord:
    verification_id: str
    request_id: str
    candidate_id: str
    declaration_id: str
    verifier_id: str
    acceptance_id: str
    package_id: str
    package_version: str
    runtime_adapter_id: str
    verified_artifact_sha256: str
    status: VerificationStatus
    feedback: str
    facts: tuple[VerificationFact, ...]
    effective_trust: str
    release_id: str | None
    signer_key_id: str | None
    created_at: datetime
    contract_version: str = VERIFICATION_RUN_VERSION

    def __post_init__(self) -> None:
        for name in (
            "verification_id", "request_id", "candidate_id", "declaration_id",
            "verifier_id", "acceptance_id", "package_id", "package_version",
            "runtime_adapter_id", "effective_trust",
        ):
            _identifier(getattr(self, name), name)
        _sha256(self.verified_artifact_sha256, "verified_artifact_sha256")
        _bounded_text(self.feedback, "feedback", 16_000, allow_empty=True)
        if not isinstance(self.status, VerificationStatus):
            raise ValueError("verification run status is invalid")
        if not self.facts or len(self.facts) > 64:
            raise ValueError("verification run requires 1-64 evidence facts")
        if any(not isinstance(item, VerificationFact) for item in self.facts):
            raise ValueError("verification run facts are invalid")
        names = tuple(item.name for item in self.facts)
        if len(set(names)) != len(names):
            raise ValueError("verification fact names must be unique")
        if (self.release_id is None) != (self.signer_key_id is None):
            raise ValueError("release and signer evidence must be present together")
        for name in ("release_id", "signer_key_id"):
            value = getattr(self, name)
            if value is not None:
                _identifier(value, name)
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("verification run time must be timezone-aware")
        if self.contract_version != VERIFICATION_RUN_VERSION:
            raise ValueError("unsupported verification run version")


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is invalid")


def _sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _bounded_text(value: str, name: str, maximum: int, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str) or "\x00" in value or len(value) > maximum:
        raise ValueError(f"{name} is invalid")
    if not allow_empty and not value.strip():
        raise ValueError(f"{name} must not be empty")


def _content_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_CONTRACTS = {
    VerificationKind.EXACT_TEXT: VerifierContractReference(
        "verifier.text.exact-v1", "acceptance.text.exact",
        "candidate.text.plain-v1", "evidence.text.exact-v1",
    ),
    VerificationKind.PYTHON_TESTS: VerifierContractReference(
        "python.deterministic-tests.v1", "acceptance.python.tests",
        "candidate.python.source-v1", "evidence.python.tests-v1",
    ),
    VerificationKind.RETRIEVAL_CITATIONS: VerifierContractReference(
        "retrieval.citations.v1", "acceptance.retrieval.citations",
        "candidate.retrieval.citations-v1", "evidence.retrieval.citations-v1",
    ),
    VerificationKind.MATH_EQUIVALENCE: VerifierContractReference(
        "math.sympy-equivalence.v1", "acceptance.math.equivalence",
        "candidate.math.expression-v1", "evidence.math.equivalence-v1",
    ),
    VerificationKind.MEDIA_ARTIFACT_TEXT: VerifierContractReference(
        "media.artifact-text.v1", "acceptance.media.artifact-text",
        "candidate.media.artifact-text-v1", "evidence.media.artifact-text-v1",
    ),
}


def contract_for_kind(kind: VerificationKind) -> VerifierContractReference:
    return _CONTRACTS[kind]
