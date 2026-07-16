"""Bounded Ollama synthesis adapter for retrieval evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, InferenceRuntime, MessageRole,
)
from fam_os.experts.retrieval_tiers import RankedRetrievalSource, SynthesisResult
from fam_os.verification.retrieval import RetrievalCitation, RetrievalClaim


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
            return _parse_synthesis(response.content, self.model_ref, sources)
        except ValueError as error:
            repair = self._request(
                query, sources, f"INVALID OUTPUT:\n{response.content}\nERROR: {error}",
            )
            return _parse_synthesis(
                self.runtime.chat(repair).content, self.model_ref, sources,
            )

    def _request(self, query, sources, feedback: str | None = None):
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


_SYSTEM_PROMPT = """Answer only from the supplied sources. Return JSON with keys
answer and claims. claims is a non-empty array of objects with text, source_id,
and quote. Every quote must be an exact, contiguous substring of that source.
source_id and quote must be non-empty strings, never null. Do not use outside
knowledge. Keep the answer concise. Never invent or rename a source identifier."""


def _user_prompt(query: str, sources: tuple[RankedRetrievalSource, ...]) -> str:
    allowed = ", ".join(item.source.source_id for item in sources)
    example_source = sources[0].source
    example_quote = example_source.content[:min(48, len(example_source.content))]
    blocks = [
        f"QUERY: {query}",
        f"ALLOWED SOURCE IDS (copy exactly): {allowed}",
        "OUTPUT SHAPE EXAMPLE USING AN ALLOWED ID: " + json.dumps({
            "answer": "concise answer",
            "claims": [{"text": "supported claim", "source_id": example_source.source_id,
                        "quote": example_quote}],
        }),
    ]
    for ranked in sources:
        blocks.append(f"SOURCE {ranked.source.source_id}:\n{ranked.source.content}")
    return "\n\n".join(blocks)


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
    claims, citations = [], []
    for index, raw in enumerate(raw_claims, 1):
        claim, citation = _claim_and_citation(index, raw, source_map)
        claims.append(claim)
        citations.append(citation)
    return SynthesisResult(answer, tuple(claims), tuple(citations), model_ref)


def _claim_and_citation(index: int, raw: object, source_map: dict):
    if not isinstance(raw, dict):
        raise ValueError("synthesis claim must be an object")
    text, source_id, quote = raw.get("text"), raw.get("source_id"), raw.get("quote")
    if not all(isinstance(value, str) and value for value in (text, source_id, quote)):
        raise ValueError("synthesis claim fields must be non-empty strings")
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
