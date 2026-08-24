# ADR 0130: Live adaptation is advisory and verification-invariant

**Status:** Accepted  
**Date:** 2026-07-17

## Context

Phase 11 supplied isolated frequency, outcome, transition, prefetch, and drift
algorithms. Phase 20.5 supplied privacy-minimized verified production outcomes,
but no installed request consumed them. Directly training on prompts, selecting
an incompatible model, shrinking context below the active prompt, or preloading
without a live resource check would turn adaptation into an authority or quality
bypass.

The production selector also ranked residency ahead of the strong escalation
tier. A resident primary model could therefore be selected again during an
escalation attempt instead of moving to the declared strong tier.

## Decision

The installed product derives immutable `LiveAdaptationSnapshot` records only
from owner-encrypted `VerifiedLearningOutcome` records. Each snapshot is local,
advisory, content-free, intent-scoped, digest-bound to every source identity,
and owner-encrypted. It contains no prompt, candidate, source, application
payload, or authority.

Live prediction uses deterministic bounded rules:

- at least two verified workflow observations are required;
- context is the verified P95 power-of-two bucket;
- the current complete prompt, output allowance, and fixed framing reserve form
  a conservative lower bound, and media requests keep the full configured
  context;
- escalation prewarm requires probability at least 0.75;
- a frequency preference requires at least two verified uses and a unique
  leader; and
- next-expert prewarm requires at least two matching transitions and confidence
  at least 0.75.

Frequency may break a tie only among signed, enabled, intent-compatible models
inside the existing policy tier. It cannot cross a tier, bypass a resource fit,
or alter a verifier. Strong escalation ranks the declared strong tier before
residency, so a loaded primary cannot defeat escalation policy.

Prewarm occurs asynchronously after the verified-learning transaction commits.
It admits at most one predicted cold model at a time, preserves two GiB of host
headroom, requests no eviction, imports only a managed or already local model,
and calls Ollama with model identity and `keep_alive` but no prompt. Completion
requires `/api/ps` residency evidence. The prediction snapshot and resulting
completed, rejected, or failed receipt are encrypted in migration 0014. Restart
reconstructs advice from the same verified observations without replaying
inference.

Routing, permissions, attempt budgets, verification declarations, candidate
binding, release assurance, application postconditions, and terminal policy are
unchanged. Adaptation can affect only an eligible model tie, context allocation,
or ahead-of-demand residency.

## Consequences

- Repeated text workflows can request substantially less context memory without
  truncating their complete current prompt.
- Repair feedback automatically raises the lower bound when it expands a prompt.
- Strong models can be ready before a predicted escalation or transition, while
  normal model loading remains the fallback.
- Every applied prediction has durable source identities and resource evidence;
  raw working content is not duplicated.
- Physical Ollama trials cover both `gemma4:26b` and
  `laguna-xs.2:q4_K_M`, including verified unload after each trial.
- Phase 20.7 must expose these snapshots and receipts, add disable/reset
  authority, measure drift, and roll back regressing advice.
