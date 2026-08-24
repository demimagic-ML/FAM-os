"""One strict parser shared by retrieval verification and final presentation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fam_os.verification.declarations import RetrievalCitationsVerification
from fam_os.verification.retrieval import (
    RetrievalCitation,
    RetrievalClaim,
    RetrievedSource,
)


@dataclass(frozen=True, slots=True)
class ParsedRetrievalClaim:
    claim_id: str
    text: str
    source: RetrievedSource
    quote: str
    citation: RetrievalCitation


@dataclass(frozen=True, slots=True)
class ParsedRetrievalCandidate:
    answer: str
    claims: tuple[ParsedRetrievalClaim, ...]

    @property
    def citations(self) -> tuple[RetrievalCitation, ...]:
        return tuple(item.citation for item in self.claims)

    @property
    def verification_claims(self) -> tuple[RetrievalClaim, ...]:
        return tuple(
            RetrievalClaim(item.claim_id, (item.citation.citation_id,))
            for item in self.claims
        )


def parse_retrieval_candidate(
    candidate: str,
    specification: RetrievalCitationsVerification,
) -> ParsedRetrievalCandidate:
    value = _json_object(candidate)
    answer, raw_claims = value["answer"], value["claims"]
    if not isinstance(answer, str) or not answer.strip() or not isinstance(raw_claims, list):
        raise ValueError("retrieval candidate requires answer and claims")
    if len(raw_claims) > 64:
        raise ValueError("retrieval candidate exceeds its claim bound")
    source_map = {item.source_id: item for item in specification.sources}
    claims = tuple(
        _claim(index, raw, source_map)
        for index, raw in enumerate(raw_claims, 1)
    )
    if not claims:
        raise ValueError("retrieval candidate requires at least one claim")
    if answer != "\n".join(item.text for item in claims):
        raise ValueError("retrieval answer must exactly equal its ordered claim text")
    return ParsedRetrievalCandidate(answer, claims)


def _claim(index: int, raw, source_map) -> ParsedRetrievalClaim:
    if not isinstance(raw, dict) or set(raw) != {"text", "source_id", "quote"}:
        raise ValueError("retrieval claim fields are invalid")
    text, source_id, quote = raw["text"], raw["source_id"], raw["quote"]
    if not all(isinstance(item, str) and item.strip() for item in (text, source_id, quote)):
        raise ValueError("retrieval claim values must be nonempty text")
    if any("\x00" in item for item in (text, source_id, quote)):
        raise ValueError("retrieval claim values contain invalid control data")
    if text != quote:
        raise ValueError("retrieval claim text must exactly equal its source quote")
    source = source_map.get(source_id)
    if source is None:
        raise ValueError("retrieval claim cites an undeclared source")
    start = source.content.find(quote)
    if start < 0:
        raise ValueError("retrieval quote is not exact source text")
    citation_id = f"citation-{index}"
    citation = RetrievalCitation(
        citation_id, source_id, start, start + len(quote), _digest(quote),
    )
    return ParsedRetrievalClaim(f"claim-{index}", text, source, quote, citation)


def _json_object(candidate: str) -> dict:
    if not isinstance(candidate, str) or len(candidate.encode("utf-8")) > 262_144:
        raise ValueError("candidate JSON exceeds its bound")
    value = json.loads(candidate)
    if not isinstance(value, dict) or set(value) != {"answer", "claims"}:
        raise ValueError("candidate JSON fields do not match the declared schema")
    return value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
