"""Bounded Ollama synthesis adapter for retrieval evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, InferenceRuntime, MessageRole,
)
from fam_os.core.production.retrieval_fallback import (
    deterministic_retrieval_candidate,
)
from fam_os.experts.retrieval_tiers import RankedRetrievalSource, SynthesisResult
from fam_os.verification.declarations import RetrievalCitationsVerification
from fam_os.verification.retrieval import RetrievalCitation, RetrievalClaim
from fam_os.verification.retrieval import (
    RetrievedSource,
    missing_retrieval_terms,
    retrieval_query_obligation,
    retrieval_terms,
)


_SourceLine = tuple[int, int, RetrievedSource, str]


@dataclass(frozen=True, slots=True)
class OllamaRetrievalSynthesizer:
    runtime: InferenceRuntime
    model_ref: str
    context_tokens: int = 4096
    max_output_tokens: int = 512

    def synthesize(
        self, query: str, sources: tuple[RankedRetrievalSource, ...],
    ) -> SynthesisResult:
        response = self.runtime.chat(self._request(query, sources))
        try:
            return _parse_query_bound_synthesis(
                response.content, query, self.model_ref, sources,
            )
        except ValueError as error:
            repair = self._request(
                query, sources, f"INVALID OUTPUT:\n{response.content}\nERROR: {error}",
            )
            repaired = self.runtime.chat(repair).content
            try:
                return _parse_query_bound_synthesis(
                    repaired, query, self.model_ref, sources,
                )
            except ValueError as repair_error:
                try:
                    return _deterministic_synthesis(query, sources, self.model_ref)
                except ValueError:
                    raise repair_error

    def _request(
        self, query: str, sources: tuple[RankedRetrievalSource, ...],
        feedback: str | None = None,
    ) -> InferenceRequest:
        user_content = _user_prompt(query, sources)
        if feedback is not None:
            user_content += "\n\nREPAIR THE OUTPUT.\n" + feedback[:4000]
        return InferenceRequest(
            model_ref=self.model_ref,
            messages=(
                InferenceMessage(MessageRole.SYSTEM, _SYSTEM_PROMPT),
                InferenceMessage(MessageRole.USER, user_content),
            ),
            context_tokens=self.context_tokens,
            max_output_tokens=self.max_output_tokens,
            json_output=True,
        )


_SYSTEM_PROMPT = """Answer only by extracting exact text from the supplied sources.
Return JSON with keys answer and claims. claims is a non-empty array of objects
with text, source_id, and quote. text and quote must be byte-for-byte identical.
Every quote must be an exact, contiguous substring of that source. answer must
equal the claim text values joined in order with one newline. Do not paraphrase,
infer, summarize, or use outside knowledge. Never invent a source identifier."""


def _user_prompt(query: str, sources: tuple[RankedRetrievalSource, ...]) -> str:
    allowed = ", ".join(item.source.source_id for item in sources)
    example_source, example_quote = _best_query_line(query, sources)
    blocks = [
        f"QUERY: {query}",
        f"ALLOWED SOURCE IDS (copy exactly): {allowed}",
        "OUTPUT SHAPE EXAMPLE USING AN ALLOWED ID: " + json.dumps({
            "answer": example_quote,
            "claims": [{"text": example_quote, "source_id": example_source.source_id,
                        "quote": example_quote}],
        }),
    ]
    for ranked in sources:
        blocks.append(f"SOURCE {ranked.source.source_id}:\n{ranked.source.content}")
    return "\n\n".join(blocks)


def _best_query_line(
    query: str, sources: tuple[RankedRetrievalSource, ...],
) -> tuple[RetrievedSource, str]:
    query_terms = set(retrieval_terms(query))
    candidates = _source_lines(sources)
    if not candidates:
        raise ValueError("retrieval sources contain no extractive text")
    _, _, source, line = max(
        candidates,
        key=lambda item: (
            len(query_terms.intersection(retrieval_terms(item[3]))),
            -item[0], -item[1],
        ),
    )
    return source, line


def _parse_query_bound_synthesis(
    content: str, query: str, model_ref: str,
    sources: tuple[RankedRetrievalSource, ...],
) -> SynthesisResult:
    result = _parse_synthesis(content, model_ref, sources)
    missing = missing_retrieval_terms(
        (result.answer,), retrieval_query_obligation(query),
    )
    if missing:
        raise ValueError(
            "synthesis answer omits required query terms: " + ", ".join(missing)
        )
    return result


def _deterministic_synthesis(
    query: str, sources: tuple[RankedRetrievalSource, ...], model_ref: str,
) -> SynthesisResult:
    specification = RetrievalCitationsVerification(
        tuple(item.source for item in sources), retrieval_query_obligation(query),
    )
    candidate = deterministic_retrieval_candidate(query, specification)
    return _parse_query_bound_synthesis(
        candidate, query, model_ref, sources,
    )


def _source_lines(
    sources: tuple[RankedRetrievalSource, ...],
) -> tuple[_SourceLine, ...]:
    return tuple(
        (source_index, line_index, ranked.source, line.strip())
        for source_index, ranked in enumerate(sources)
        for line_index, line in enumerate(ranked.source.content.splitlines())
        if line.strip()
    )


def _parse_synthesis(
    content: str, model_ref: str, sources: tuple[RankedRetrievalSource, ...],
) -> SynthesisResult:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("synthesis response must be JSON") from exc
    answer = payload.get("answer")
    raw_claims = payload.get("claims")
    if not isinstance(answer, str) or not isinstance(raw_claims, list) or not raw_claims:
        raise ValueError("synthesis JSON requires answer and claims")
    source_map = {item.source.source_id: item.source for item in sources}
    claims, citations, claim_texts = [], [], []
    for index, raw in enumerate(raw_claims, 1):
        claim, citation = _claim_and_citation(index, raw, source_map)
        claims.append(claim)
        citations.append(citation)
        assert isinstance(raw, dict)
        claim_texts.append(raw["text"])
    if answer != "\n".join(claim_texts):
        raise ValueError("synthesis answer must exactly equal its ordered claim text")
    return SynthesisResult(answer, tuple(claims), tuple(citations), model_ref)


def _claim_and_citation(
    index: int, raw: object, source_map: dict[str, RetrievedSource],
) -> tuple[RetrievalClaim, RetrievalCitation]:
    if not isinstance(raw, dict):
        raise ValueError("synthesis claim must be an object")
    text, source_id, quote = raw.get("text"), raw.get("source_id"), raw.get("quote")
    if not all(isinstance(value, str) and value for value in (text, source_id, quote)):
        raise ValueError("synthesis claim fields must be non-empty strings")
    if text != quote:
        raise ValueError("synthesis claim text must exactly equal its source quote")
    assert isinstance(source_id, str)
    assert isinstance(quote, str)
    source = source_map.get(source_id)
    if source is None:
        raise ValueError("synthesis cited a source outside the ranked set")
    start = source.content.find(quote)
    if start < 0:
        raise ValueError("synthesis quote is not an exact source substring")
    citation_id = f"citation-{index}"
    citation = RetrievalCitation(
        citation_id, source_id, start, start + len(quote), _sha256(quote),
    )
    return RetrievalClaim(f"claim-{index}", (citation_id,)), citation


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
