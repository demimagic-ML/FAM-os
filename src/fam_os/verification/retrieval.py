"""Exact retrieval citation and source-provenance verification."""

import hashlib
from dataclasses import dataclass


RETRIEVAL_VERIFICATION_CONTRACT_VERSION = "fam.verifier.retrieval/v1alpha1"


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    source_id: str
    locator: str
    content: str
    content_sha256: str
    provenance_id: str


@dataclass(frozen=True, slots=True)
class RetrievalCitation:
    citation_id: str
    source_id: str
    start_character: int
    end_character: int
    quoted_text_sha256: str


@dataclass(frozen=True, slots=True)
class RetrievalClaim:
    claim_id: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalVerificationReport:
    verification_id: str
    verified_claim_ids: tuple[str, ...]
    rejected_claim_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    passed: bool
    contract_version: str = RETRIEVAL_VERIFICATION_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class RetrievalCitationVerifier:
    def verify(self, verification_id, sources, citations, claims) -> RetrievalVerificationReport:
        source_map = {item.source_id: item for item in sources}
        citation_map = {item.citation_id: item for item in citations}
        valid, reasons = set(), set()
        for citation in citations:
            source = source_map.get(citation.source_id)
            if source is None or not _source_valid(source):
                reasons.add("citation.source_untrusted")
                continue
            if not 0 <= citation.start_character < citation.end_character <= len(source.content):
                reasons.add("citation.locator_invalid")
                continue
            span = source.content[citation.start_character:citation.end_character]
            if _sha256(span) != citation.quoted_text_sha256:
                reasons.add("citation.quote_digest_mismatch")
                continue
            valid.add(citation.citation_id)
        verified, rejected = [], []
        for claim in claims:
            if claim.citation_ids and all(item in valid and item in citation_map for item in claim.citation_ids):
                verified.append(claim.claim_id)
            else:
                rejected.append(claim.claim_id)
                reasons.add("claim.citation_missing_or_invalid")
        passed = bool(claims) and not rejected
        return RetrievalVerificationReport(
            verification_id, tuple(verified), tuple(rejected), tuple(sorted(reasons)), passed,
        )


def _source_valid(source: RetrievedSource) -> bool:
    return bool(source.source_id.strip() and source.locator.strip() and source.provenance_id.strip()) and _sha256(source.content) == source.content_sha256


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
