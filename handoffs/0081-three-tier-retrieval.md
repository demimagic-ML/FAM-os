# Handoff 0081: Phase 9.4 three-tier retrieval

## Completed

- Added the provider-neutral embedding contracts and live Ollama `/api/embed` implementation.
- Added a deterministic semantic-plus-lexical reranker with stable source-ID tie-breaking.
- Added bounded Ollama synthesis with exact quote/source parsing and at most one actionable repair.
- Added separately packaged embedding, reranking, and cited-synthesis experts.
- Kept release authority in the existing exact-span citation verifier.
- Added strict public result/evidence schemas and rendered 94 schema artifacts.
- Ran the live workstation proof with Nomic and Llama 3.2; the cited answer passed and was released.

## Evidence

- `artifacts/expert_fabric/phase9.4/retrieval-tiers-workstation.json`
- `tests/integration/test_retrieval_tier_evidence.py`
- `tests/unit/test_retrieval_tiers.py`
- `tests/unit/test_ollama_runtime.py`
- `docs/protocols/THREE_TIER_RETRIEVAL.md`
- `docs/decisions/0080-three-tier-retrieval.md`

## Next

Start Phase 9.5 by defining the mathematics reasoning/solver boundary. Generative reasoning must remain advisory; exact arithmetic and symbolic results need deterministic solver verification.
