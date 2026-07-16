# Three-tier retrieval

Phase 9.4 separates retrieval into three independently identifiable expert tiers:

1. `expert.retrieval.nomic-embed-text` embeds the query and every candidate source through the provider-neutral `EmbeddingRuntime` port.
2. `expert.retrieval.deterministic-reranker-v1` combines cosine similarity with a bounded lexical score. Equal scores are ordered by immutable source ID, so ranking is repeatable.
3. `expert.retrieval.llama3.2-synthesis` produces a bounded JSON answer and exact source quotes. One repair is allowed and receives the invalid output, the validation error, and the complete ranked source set.

The synthesis tier has no release authority. The existing `RetrievalCitationVerifier` independently checks source content digests, provenance, exact character spans, and quote digests. FAM releases the answer only when every claim has valid citations.

## Live workstation proof

Run:

```bash
PYTHONPATH=src python3 tools/run_retrieval_tiers.py \
  --fixture tests/fixtures/retrieval_tiers/workstation-v1.json \
  --output artifacts/expert_fabric/phase9.4/retrieval-tiers-workstation.json
```

The checked evidence records Ollama-observed artifact digests, a 768-dimensional Nomic embedding, deterministic ranking, the exact cited source IDs, verified claim IDs, and the release decision. The proof uses `nomic-embed-text:latest` and `llama3.2:3b` installed on the test workstation.

## Failure behavior

- Wrong vector counts or dimensions stop before reranking.
- Empty or invented source IDs stop synthesis.
- Non-exact quotes stop synthesis before verification.
- Tampered source content, invalid spans, or missing claim citations cause the verifier to withhold release.
