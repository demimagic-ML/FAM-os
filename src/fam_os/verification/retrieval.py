"""Exact extractive retrieval, query coverage, and source verification."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass


RETRIEVAL_VERIFICATION_CONTRACT_VERSION = "fam.verifier.retrieval/v1alpha1"

_FAM_OS_LONG = re.compile(
    r"\bfor\s+all\s+mankind\s+operating\s+system\b",
    re.IGNORECASE,
)
_FAM_OS = re.compile(r"\bfam[\s_-]*os\b", re.IGNORECASE)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_STOP_WORDS = frozenset({
    "a", "about", "an", "and", "answer", "are", "as", "at", "be", "been",
    "being", "briefly", "by", "can", "concise", "could", "current", "describe",
    "did", "do", "does", "exact", "exactly", "explain", "for", "from", "give", "hello",
    "help", "how", "i", "in", "into", "is", "it", "its", "me", "my", "of",
    "on", "one", "or", "please", "project", "reply", "say", "sentence", "short",
    "show", "tell", "that", "the", "their", "these", "this", "those", "to", "us",
    "was", "we", "were", "what", "when", "where", "which", "who", "why", "will",
    "with", "would", "you", "your", "document", "documents", "file", "files",
    "folder", "repository", "statement", "workspace",
})


@dataclass(frozen=True, slots=True)
class RetrievalQueryObligation:
    """Digest-bound lexical anchors that a verified extractive answer must cover."""

    query_sha256: str
    required_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.query_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.query_sha256
        ):
            raise ValueError("retrieval query digest must be lowercase SHA-256")
        if not self.required_terms or len(self.required_terms) > 32:
            raise ValueError("retrieval query requires 1-32 significant terms")
        if len(set(self.required_terms)) != len(self.required_terms):
            raise ValueError("retrieval query terms must be unique")
        if any(
            term != _canonical_term(term) or len(term) > 64
            for term in self.required_terms
        ):
            raise ValueError("retrieval query terms must be canonical")


def retrieval_query_obligation(query: str) -> RetrievalQueryObligation:
    """Create a bounded, deterministic obligation from the exact user query bytes."""

    if not isinstance(query, str) or not query.strip() or "\x00" in query:
        raise ValueError("retrieval query must be strict nonempty text")
    if len(query.encode("utf-8")) > 16_000:
        raise ValueError("retrieval query exceeds its byte bound")
    terms = retrieval_terms(query)
    if not terms:
        raise ValueError("retrieval query has no significant terms")
    if len(terms) > 32:
        raise ValueError("retrieval query has more than 32 significant terms")
    return RetrievalQueryObligation(_sha256(query), terms)


def retrieval_terms(value: str) -> tuple[str, ...]:
    """Return ordered unique canonical terms for deterministic coverage checks."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = _FAM_OS_LONG.sub(" famos ", normalized)
    normalized = _FAM_OS.sub(" famos ", normalized)
    values: list[str] = []
    for raw in _WORD.findall(normalized):
        if raw in _STOP_WORDS or len(raw) < 3:
            continue
        term = _canonical_term(raw)
        if term and term not in values:
            values.append(term)
    return tuple(values)


def missing_retrieval_terms(
    values: tuple[str, ...], obligation: RetrievalQueryObligation,
) -> tuple[str, ...]:
    observed = {
        term
        for value in values
        for term in retrieval_terms(value)
    }
    return tuple(term for term in obligation.required_terms if term not in observed)


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    source_id: str
    locator: str
    content: str
    content_sha256: str
    provenance_id: str

    def __post_init__(self) -> None:
        for name in ("source_id", "locator", "provenance_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError(f"retrieval {name} must be strict nonempty text")
        if not self.content or "\x00" in self.content:
            raise ValueError("retrieval source content must be strict nonempty text")
        if len(self.content_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.content_sha256
        ):
            raise ValueError("retrieval source digest must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class RetrievalCitation:
    citation_id: str
    source_id: str
    start_character: int
    end_character: int
    quoted_text_sha256: str

    def __post_init__(self) -> None:
        if not self.citation_id.strip() or not self.source_id.strip():
            raise ValueError("retrieval citation identity is required")
        if self.start_character < 0 or self.end_character <= self.start_character:
            raise ValueError("retrieval citation span is invalid")
        if len(self.quoted_text_sha256) != 64:
            raise ValueError("retrieval quote digest must be SHA-256")


@dataclass(frozen=True, slots=True)
class RetrievalClaim:
    claim_id: str
    citation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.citation_ids:
            raise ValueError("retrieval claim requires identity and citations")
        if len(set(self.citation_ids)) != len(self.citation_ids):
            raise ValueError("retrieval claim citations must be unique")


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
    def verify(
        self, verification_id, sources, citations, claims,
        query: RetrievalQueryObligation | None = None,
    ) -> RetrievalVerificationReport:
        source_map = {item.source_id: item for item in sources}
        citation_map = {item.citation_id: item for item in citations}
        valid, reasons = {}, set()
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
            valid[citation.citation_id] = span
        verified, rejected = [], []
        for claim in claims:
            citations_valid = bool(claim.citation_ids) and all(
                item in valid and item in citation_map for item in claim.citation_ids
            )
            if not citations_valid:
                rejected.append(claim.claim_id)
                reasons.add("claim.citation_missing_or_invalid")
                continue
            verified.append(claim.claim_id)
        missing_terms: tuple[str, ...] = ()
        if query is None:
            reasons.add("query.obligation_missing")
        else:
            source_missing = missing_retrieval_terms(
                tuple(item.content for item in sources), query,
            )
            missing_terms = missing_retrieval_terms(
                tuple(
                    valid[citation_id]
                    for claim in claims if claim.claim_id in verified
                    for citation_id in claim.citation_ids
                ),
                query,
            )
            if source_missing:
                reasons.add("query.source_coverage_missing")
            if missing_terms:
                reasons.add("query.answer_coverage_missing")
        passed = query is not None and bool(claims) and not rejected and not reasons
        return RetrievalVerificationReport(
            verification_id, tuple(verified), tuple(rejected), tuple(sorted(reasons)), passed,
        )


def _source_valid(source: RetrievedSource) -> bool:
    return bool(source.source_id.strip() and source.locator.strip() and source.provenance_id.strip()) and _sha256(source.content) == source.content_sha256


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_term(value: str) -> str:
    if not value or not value.isalnum():
        return ""
    if value == "famos":
        return value
    if value.isascii():
        if len(value) > 5 and value.endswith("ies"):
            value = value[:-3] + "y"
        elif len(value) > 5 and value.endswith("ing"):
            value = value[:-3]
            if len(value) > 2 and value[-1] == value[-2]:
                value = value[:-1]
        elif len(value) > 4 and value.endswith("ed"):
            value = value[:-2]
        elif len(value) > 3 and value.endswith("s") and not value.endswith("ss"):
            value = value[:-1]
        if len(value) > 4 and value.endswith("e"):
            value = value[:-1]
    return value
