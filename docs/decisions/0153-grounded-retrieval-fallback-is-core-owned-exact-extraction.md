# ADR 0153: Grounded retrieval fallback is Core-owned exact extraction

Status: Accepted

## Context

The production retrieval verifier correctly rejected a model response whose
citation was exact but whose answer did not satisfy the current query. The
benchmark adapter already had a deterministic extractive fallback, but the
installed Core path could exhaust inference attempts and withhold an answer
even when the authorized source contained an exact obligation-matching line.

Putting fallback logic in the signed verifier module changed the verifier code
digest. Existing signed declarations then failed closed for an unrelated
reason, conflating candidate construction with acceptance identity.

## Decision

Query-aware deterministic extraction belongs to the production Core boundary,
not the signed verifier package.

- A fallback is eligible only for a query-bound retrieval declaration whose
  exact query obligation is present.
- It may return only an exact line from a declared authorized source. It cannot
  paraphrase, synthesize, or add model knowledge.
- A valid model candidate is preserved unchanged. The deterministic candidate
  is used only when the model output is invalid and an exact eligible source
  line exists.
- If no exact eligible line exists, Core retains the original candidate and the
  signed verifier decides normally; no fallback can manufacture a pass.
- The signed retrieval verifier remains responsible for provenance, selected
  source coverage, cited-span coverage, and query-obligation acceptance. Its
  digest and declaration identity are unchanged.

## Consequences

- Installed document grounding can recover from weak synthesis without
  weakening or bypassing acceptance.
- Exact source text, query binding, and signed verification remain mandatory.
- Candidate construction can evolve independently from verifier package
  identity.
- Benchmark and production adapters share the same Core helper instead of
  maintaining behaviorally different fallbacks.

## Alternatives considered

- Modifying the signed verifier was rejected because it invalidated existing
  signed declarations and mixed construction with acceptance.
- Accepting any cited sentence was rejected because citation provenance alone
  does not prove query relevance.
- Asking a stronger model unconditionally was rejected because exact authorized
  bytes already provide a deterministic, lower-cost answer when available.

## Evidence

- `src/fam_os/core/production/retrieval_fallback.py`
- `src/fam_os/core/production/execution_worker.py`
- `src/fam_os/adapters/ollama/retrieval_synthesizer.py`
- `src/fam_os/verification/retrieval_candidate.py`
- `tests/unit/test_production_retrieval_fallback.py`
- `tests/unit/test_production_task_gateway.py`
- `artifacts/product/phase23/installed-matrix/phase23-installed-20260718-11/installed-scenario-matrix.json`
- `artifacts/product/phase23/hardware-matrix/phase23-hardware-20260718-06/installed-hardware-matrix.json`
