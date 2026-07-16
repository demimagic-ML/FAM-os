# ADR 0059: Estimate context memory by model execution strategy

**Status:** Accepted  
**Date:** 2026-07-16

## Context

FAM's existing resource manifests have one estimated resident byte count and one
context-token ceiling. That cannot explain how request memory grows, distinguish
prompt from output reservation, handle concurrent sequences, or avoid adding
context to an Ollama resident measurement that may already include it. FAM also
packages both autoregressive generators and a bidirectional embedding encoder.

## Decision

Add strict model-profile, reservation, and estimate roots under
`fam.scheduler.context-memory/v1alpha1`. Require estimates to exclude model
resident bytes and expose every context component, safety margin, and assumption.

Use grouped-query KV-cache arithmetic for autoregressive models. Use hidden
buffers plus a quadratic full-attention peak for encoders. Reserve prompt and
possible output separately, multiply sequence-owned components by concurrency,
and reject capacity overflow before placement.

Keep provider metadata behind an adapter. The Ollama adapter observes `/api/show`
and applies only explicit conservative fallbacks: all attention heads when KV
heads are absent, divisible embedding-per-head dimensions when key/value widths
are absent, f16-width cache unless deployment policy says otherwise, and no
sliding-window discount without a calibrated layer pattern.

## Consequences

- Later admission can add weight-only model residency and context exactly once.
- Output growth and concurrency are visible before inference starts.
- Encoder memory cannot be underestimated using a linear decoder formula.
- Laguna and Gemma remain usable candidates, but Gemma's missing metadata yields
  a deliberately large safe bound rather than optimistic placement.
- Package ceilings remain authoritative even when native model metadata advertises
  a much larger context.
- The strict schema catalog increases from 52 to 55 roots.

## Alternatives considered

1. Fixed bytes per token for every model: rejected for GQA and encoder mismatch.
2. Treat package resident bytes as weights: rejected because current values came
   from runtime residency evidence and may include context/overhead.
3. Apply sliding-window metadata automatically: rejected because layer patterns
   are absent for the local strong models.
4. Empirically fit only this Ollama build: rejected as the sole contract because
   scheduler semantics must remain provider-neutral; calibrated profiles remain
   an explicit supported source.
5. Ignore output tokens: rejected because generation grows KV cache until stop.

## Evidence

- `src/fam_os/scheduler/context_contracts.py`
- `src/fam_os/scheduler/context_estimator.py`
- `src/fam_os/adapters/ollama/context_profile.py`
- `configs/context_profiles/reference-models.json`
- `tests/unit/test_context_memory_estimator.py`
- `tests/unit/test_ollama_context_profile.py`
- `tests/integration/test_reference_context_profiles.py`
- `artifacts/scheduler/phase7.2/reference-context-estimates/`
