"""Embedding, reranking, and verified synthesis retrieval tiers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from fam_os.core.ports.embedding import EmbeddingRequest, EmbeddingRuntime
from fam_os.verification.retrieval import (
    RetrievalCitation, RetrievalCitationVerifier, RetrievalClaim,
    RetrievalVerificationReport, RetrievedSource,
)

RETRIEVAL_TIERS_CONTRACT_VERSION = "fam.expert.retrieval-tiers/v1alpha1"


@dataclass(frozen=True, slots=True)
class RankedRetrievalSource:
    source: RetrievedSource
    semantic_score: float
    lexical_score: float
    combined_score: float
    rank: int


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    answer: str
    claims: tuple[RetrievalClaim, ...]
    citations: tuple[RetrievalCitation, ...]
    model_ref: str

    def __post_init__(self) -> None:
        if not self.answer.strip() or not self.model_ref.strip() or not self.claims:
            raise ValueError("synthesis requires answer, model, and claims")


@dataclass(frozen=True, slots=True)
class VerifiedRetrievalResult:
    query: str
    ranked_sources: tuple[RankedRetrievalSource, ...]
    synthesis: SynthesisResult
    verification: RetrievalVerificationReport
    released: bool
    contract_version: str = RETRIEVAL_TIERS_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.released != self.verification.passed:
            raise ValueError("retrieval release must match citation verification")


class RetrievalSynthesizer(Protocol):
    def synthesize(
        self, query: str, sources: tuple[RankedRetrievalSource, ...],
    ) -> SynthesisResult: ...


@dataclass(frozen=True, slots=True)
class VerifiedRetrievalPipeline:
    embedding_runtime: EmbeddingRuntime
    embedding_model_ref: str
    synthesizer: RetrievalSynthesizer
    verifier: RetrievalCitationVerifier = RetrievalCitationVerifier()
    semantic_weight: float = 0.8

    def run(
        self, query: str, sources: tuple[RetrievedSource, ...], top_k: int = 3,
    ) -> VerifiedRetrievalResult:
        if not query.strip() or not sources or top_k <= 0:
            raise ValueError("query, sources, and bounded top_k are required")
        response = self.embedding_runtime.embed(EmbeddingRequest(
            self.embedding_model_ref,
            (query,) + tuple(source.content for source in sources),
        ))
        if len(response.vectors) != len(sources) + 1:
            raise ValueError("embedding runtime returned the wrong vector count")
        ranked = self._rank(query, sources, response.vectors)[:min(top_k, len(sources))]
        synthesis = self.synthesizer.synthesize(query, ranked)
        report = self.verifier.verify(
            "retrieval-release", sources, synthesis.citations, synthesis.claims,
        )
        return VerifiedRetrievalResult(
            query, ranked, synthesis, report, report.passed,
        )

    def _rank(self, query, sources, vectors) -> tuple[RankedRetrievalSource, ...]:
        query_terms = set(query.casefold().split())
        scored = []
        for source, vector in zip(sources, vectors[1:], strict=True):
            semantic = _cosine(vectors[0], vector)
            source_terms = set(source.content.casefold().split())
            lexical = len(query_terms & source_terms) / max(1, len(query_terms))
            combined = self.semantic_weight * semantic + (1 - self.semantic_weight) * lexical
            scored.append((source, semantic, lexical, combined))
        scored.sort(key=lambda item: (-item[3], item[0].source_id))
        return tuple(RankedRetrievalSource(*item, rank=index) for index, item in enumerate(scored, 1))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    if denominator == 0:
        return 0.0
    return sum(x * y for x, y in zip(left, right, strict=True)) / denominator
