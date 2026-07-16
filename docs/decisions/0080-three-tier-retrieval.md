# ADR 0080: Separate retrieval into embedding, reranking, and verified synthesis

- Status: accepted
- Date: 2026-07-16

## Decision

FAM retrieval uses a provider-neutral embedding port, a deterministic hybrid reranker, and a bounded model synthesizer as separate expert packages. Synthesized output is not user-visible until the independent retrieval citation verifier accepts every claim.

The Ollama adapter uses `/api/embed` for batch embeddings. The initial workstation synthesizer is the already installed `llama3.2:3b`; it may make one bounded repair attempt with actionable validation feedback. The reranker remains deterministic and authority-free.

## Consequences

- Embedding or synthesis runtimes can be replaced without changing retrieval policy.
- Ranking is reproducible and cheaper than using another generative model.
- A fluent answer cannot bypass source provenance and exact-span verification.
- The synthesis repair adds bounded latency but does not weaken acceptance.
