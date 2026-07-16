#!/usr/bin/env python3
"""Run the live Phase 9.4 three-tier retrieval proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.ollama import OllamaModelCatalog, OllamaRuntime, OllamaSettings
from fam_os.adapters.ollama.retrieval_synthesizer import OllamaRetrievalSynthesizer
from fam_os.core.ports.embedding import EmbeddingRequest
from fam_os.experts.retrieval_evidence import RetrievalTierEvidence
from fam_os.experts.retrieval_tiers import VerifiedRetrievalPipeline
from fam_os.verification.retrieval import RetrievedSource


class RecordingEmbeddingRuntime:
    def __init__(self, runtime):
        self.runtime = runtime
        self.dimension = 0

    def embed(self, request: EmbeddingRequest):
        response = self.runtime.embed(request)
        self.dimension = len(response.vectors[0])
        return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    sources = tuple(_source(raw) for raw in fixture["sources"])
    settings = OllamaSettings(args.ollama_url, 180)
    runtime = OllamaRuntime(settings)
    catalog = OllamaModelCatalog(settings)
    embedding_artifact = catalog.observe("nomic-embed-text:latest")
    synthesis_artifact = catalog.observe("llama3.2:3b")
    recording = RecordingEmbeddingRuntime(runtime)
    pipeline = VerifiedRetrievalPipeline(
        recording, "nomic-embed-text:latest",
        OllamaRetrievalSynthesizer(runtime, "llama3.2:3b"),
    )
    result = pipeline.run(fixture["query"], sources, fixture["top_k"])
    evidence = RetrievalTierEvidence(
        "phase9.4-workstation-v1", "expert.retrieval.nomic-embed-text",
        "nomic-embed-text:latest", embedding_artifact.digest.value, recording.dimension,
        "expert.retrieval.deterministic-reranker-v1",
        tuple(item.source.source_id for item in result.ranked_sources),
        "expert.retrieval.llama3.2-synthesis", "llama3.2:3b",
        synthesis_artifact.digest.value,
        tuple(item.source_id for item in result.synthesis.citations),
        result.verification.verified_claim_ids, result.synthesis.answer,
        result.released,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n")


def _source(raw: dict) -> RetrievedSource:
    content = raw["content"]
    return RetrievedSource(
        raw["source_id"], raw["locator"], content,
        hashlib.sha256(content.encode()).hexdigest(), raw["provenance_id"],
    )


if __name__ == "__main__":
    main()
