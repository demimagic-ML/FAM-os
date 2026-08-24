"""Declared deterministic verification policies for production inference."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from fam_os.core.production.contracts import ModelIntent
from fam_os.verification import VerificationRunRecord
from fam_os.verification import (
    ExactTextVerification,
    VerificationDeclaration,
    contract_for_kind,
)


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    available: bool
    passed: bool
    verifier_id: str
    acceptance_id: str
    feedback: str
    run_record: VerificationRunRecord | None = None

    def __post_init__(self) -> None:
        if self.available and not self.verifier_id.strip():
            raise ValueError("available verification requires a verifier ID")
        if self.passed and not self.available:
            raise ValueError("unavailable verification cannot pass")
        if self.available and not self.acceptance_id.strip():
            raise ValueError("available verification requires acceptance identity")
        if len(self.feedback) > 16_000:
            raise ValueError("verification feedback is too large")


class DeclaredVerifier(Protocol):
    def verify(
        self, intent: ModelIntent, request, candidate_id: str, candidate: str,
    ) -> VerificationDecision: ...


class VerificationFailureObserver(Protocol):
    def verification_failed(self, record, decision: VerificationDecision) -> None: ...


class DeclaredTextVerifier:
    """Verify only exact-output requests; ordinary prose remains unverified."""

    def verify(self, intent: ModelIntent, request, _candidate_id: str, candidate: str) -> VerificationDecision:
        match = _EXACT.fullmatch(" ".join(request.prompt.split()))
        acceptance_id = "acceptance.text.exact"
        if match is None:
            return VerificationDecision(
                False, False, "", acceptance_id,
                "No deterministic verifier is declared for this request.",
            )
        expected = match.group("value").strip().strip("'\"")
        passed = candidate.strip() == expected
        feedback = (
            "Exact output matched the requested bytes."
            if passed
            else f"Expected exact output {expected!r}; received {candidate.strip()!r}."
        )
        return VerificationDecision(
            True, passed, "text.exact-output.v1", acceptance_id, feedback,
        )


def exact_text_declaration(
    request_id: str, prompt: str,
) -> VerificationDeclaration | None:
    match = _EXACT.fullmatch(" ".join(prompt.split()))
    if match is None:
        return None
    specification = ExactTextVerification(
        match.group("value").strip().strip("'\""),
    )
    return VerificationDeclaration(
        f"declaration-{request_id}", request_id,
        contract_for_kind(specification.kind), specification,
    )


_EXACT = re.compile(
    r"(?:please\s+)?(?:reply|respond|output|return)\s+with\s+exactly\s+(?P<value>.+?)[.!]?",
    re.IGNORECASE,
)
