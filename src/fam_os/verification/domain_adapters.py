"""Explicit deterministic adapters for production verifier declarations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fam_os.verification.activation import ActivatedVerifier
from fam_os.verification.contracts import (
    VerificationRequest,
    VerificationStatus,
)
from fam_os.verification.declarations import (
    ExactTextVerification,
    MathEquivalenceVerification,
    MediaArtifactTextVerification,
    PythonTestsVerification,
    RetrievalCitationsVerification,
    VerificationDeclaration,
    VerificationFact,
)
from fam_os.verification.math_contracts import MathVerificationRequest
from fam_os.verification.math_sympy import SympyMathVerifier
from fam_os.verification.media import MediaArtifactTextVerifier
from fam_os.verification.python.bundles import TrustedPythonTests
from fam_os.verification.python.verifier import PythonVerifier
from fam_os.verification.retrieval import (
    RetrievalCitationVerifier,
    missing_retrieval_terms,
)
from fam_os.verification.retrieval_candidate import parse_retrieval_candidate


@dataclass(frozen=True, slots=True)
class DomainVerificationResult:
    status: VerificationStatus
    feedback: str
    facts: tuple[VerificationFact, ...]


class ProductionVerifierAdapters:
    def __init__(self, sandbox) -> None:
        self._sandbox = sandbox

    def verify(
        self,
        activation: ActivatedVerifier,
        declaration: VerificationDeclaration,
        candidate: str,
        verification_id: str,
    ) -> DomainVerificationResult:
        binding = activation.package.binding
        key = (binding.runtime_adapter_id, binding.entry_point)
        handler = self._handlers().get(key)
        if handler is None:
            return _error("runtime.entry_point_not_allowed")
        try:
            return handler(declaration.specification, candidate, verification_id)
        except ImportError:
            return _error("runtime.dependency_unavailable")
        except OSError:
            return _error("runtime.input_unavailable")
        except (ArithmeticError, KeyError, TypeError, ValueError, SyntaxError) as error:
            return _failed(f"Candidate did not satisfy its declared schema: {error}")

    def _handlers(self):
        return {
            (
                "python.in-process/v1",
                "fam_os.verification.domain_adapters:verify_exact_text",
            ): self._exact,
            (
                "bubblewrap.python/v1",
                "fam_os.verification.domain_adapters:verify_python_tests",
            ): self._python,
            (
                "python.in-process/v1",
                "fam_os.verification.domain_adapters:verify_retrieval_citations",
            ): self._retrieval,
            (
                "sympy.safe-ast/v1",
                "fam_os.verification.domain_adapters:verify_math_equivalence",
            ): self._math,
            (
                "python.in-process/v1",
                "fam_os.verification.domain_adapters:verify_media_artifact_text",
            ): self._media,
        }

    def _exact(self, specification, candidate, _verification_id):
        if not isinstance(specification, ExactTextVerification):
            raise TypeError("exact-text verifier received the wrong specification")
        passed = candidate == specification.expected_text
        feedback = (
            "Exact candidate bytes matched the declaration."
            if passed else
            f"Expected exact bytes {specification.expected_text!r}; received {candidate!r}."
        )
        return _result(passed, feedback, (
            VerificationFact("expected_sha256", _text_digest(specification.expected_text)),
            VerificationFact("candidate_sha256", _text_digest(candidate)),
        ))

    def _python(self, specification, candidate, verification_id):
        if not isinstance(specification, PythonTestsVerification):
            raise TypeError("Python verifier received the wrong specification")
        if _text_digest(specification.test_source) != specification.test_source_sha256:
            raise ValueError("trusted Python test source digest changed")
        report = PythonVerifier(
            self._sandbox,
            TrustedPythonTests(specification.bundle_id, specification.test_source),
        ).verify(VerificationRequest(verification_id, candidate))
        details = report.failure_details(6_000)
        feedback = (
            "All declared deterministic Python tests passed."
            if report.passed else
            (
                f"Python verification failed at {report.stage}: {report.reason}.\n"
                f"Trusted acceptance test source:\n{specification.test_source}\n"
                f"Observed failure:\n{details}"
            )[:16_000]
        )
        facts = (
            VerificationFact("bundle_id", specification.bundle_id),
            VerificationFact("test_source_sha256", specification.test_source_sha256),
            VerificationFact("stage", report.stage),
            VerificationFact("reason", report.reason),
            VerificationFact("wall_seconds", f"{report.wall_seconds:.9f}"),
        )
        return DomainVerificationResult(report.status, feedback, facts)

    def _retrieval(self, specification, candidate, verification_id):
        if not isinstance(specification, RetrievalCitationsVerification):
            raise TypeError("retrieval verifier received the wrong specification")
        parsed = parse_retrieval_candidate(candidate, specification)
        report = RetrievalCitationVerifier().verify(
            verification_id, specification.sources,
            parsed.citations, parsed.verification_claims, specification.query,
        )
        feedback = (
            "Every answer claim is exact authorized source text and covers the query obligation."
            if report.passed else
            "Retrieval verification failed: " + ", ".join(report.reason_codes)
        )
        query_sha256 = (
            specification.query.query_sha256
            if specification.query is not None else "unbound"
        )
        required_terms = (
            ",".join(specification.query.required_terms)
            if specification.query is not None else "unbound"
        )
        missing_terms = (
            missing_retrieval_terms(
                tuple(item.text for item in parsed.claims), specification.query,
            )
            if specification.query is not None else ()
        )
        return _result(report.passed, feedback, (
            VerificationFact("answer_sha256", _text_digest(parsed.answer)),
            VerificationFact("claim_count", str(len(parsed.claims))),
            VerificationFact("verified_claim_count", str(len(report.verified_claim_ids))),
            VerificationFact("query_sha256", query_sha256),
            VerificationFact("query_required_terms", required_terms),
            VerificationFact(
                "query_missing_terms", ",".join(missing_terms) or "none",
            ),
            VerificationFact("reason_codes", ",".join(report.reason_codes) or "accepted"),
        ))

    def _math(self, specification, candidate, verification_id):
        if not isinstance(specification, MathEquivalenceVerification):
            raise TypeError("math verifier received the wrong specification")
        expression = _json_object(candidate, {"expression"})["expression"]
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError("math candidate expression must be nonempty text")
        report = SympyMathVerifier().verify(MathVerificationRequest(
            verification_id, expression, specification.reference_expression,
            specification.variable, specification.sample_points,
            specification.absolute_tolerance, specification.precision_digits,
        ))
        feedback = (
            "Symbolic equivalence and every high-precision sample passed."
            if report.passed else
            f"Math verification failed; counterexample={report.counterexample_point!r}; "
            f"maximum_absolute_error={report.maximum_absolute_error}."
        )
        return _result(report.passed, feedback, (
            VerificationFact("symbolic_equivalent", str(report.symbolic_equivalent).lower()),
            VerificationFact("numerical_passed", str(report.numerical_passed).lower()),
            VerificationFact("maximum_absolute_error", report.maximum_absolute_error),
            VerificationFact("sample_count", str(report.sample_count)),
        ))

    def _media(self, specification, candidate, verification_id):
        if not isinstance(specification, MediaArtifactTextVerification):
            raise TypeError("media verifier received the wrong specification")
        value = _json_object(candidate, {"artifact_sha256", "observed_text"})
        digest, observed = value["artifact_sha256"], value["observed_text"]
        if not isinstance(digest, str) or not isinstance(observed, str):
            raise ValueError("media candidate fields must be text")
        report = MediaArtifactTextVerifier().verify(
            verification_id, specification, digest, observed,
        )
        feedback = (
            "Media bytes, candidate binding, and observed text matched exactly."
            if report.passed else f"Media verification failed: {report.reason_code}."
        )
        return _result(report.passed, feedback, (
            VerificationFact("artifact_sha256", report.artifact_sha256),
            VerificationFact("artifact_bytes", str(report.artifact_bytes)),
            VerificationFact("artifact_matched", str(report.artifact_matched).lower()),
            VerificationFact("text_matched", str(report.text_matched).lower()),
        ))


def _json_object(candidate: str, fields: set[str]) -> dict:
    if len(candidate) > 262_144:
        raise ValueError("candidate JSON exceeds its bound")
    value = json.loads(candidate)
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("candidate JSON fields do not match the declared schema")
    return value


def _result(passed, feedback, facts):
    return DomainVerificationResult(
        VerificationStatus.PASSED if passed else VerificationStatus.FAILED,
        feedback[:16_000], facts,
    )


def _failed(feedback: str) -> DomainVerificationResult:
    return DomainVerificationResult(
        VerificationStatus.FAILED, feedback[:16_000],
        (VerificationFact("reason", "candidate.schema_invalid"),),
    )


def _error(reason: str) -> DomainVerificationResult:
    return DomainVerificationResult(
        VerificationStatus.ERROR, reason,
        (VerificationFact("reason", reason),),
    )


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
