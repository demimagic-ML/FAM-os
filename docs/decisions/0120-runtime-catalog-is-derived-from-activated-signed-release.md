# ADR 0120: Runtime catalog is derived from the activated signed release

**Status:** Accepted  
**Date:** 2026-07-17

## Context

Reading extracted expert JSON directly would let runtime configuration drift
from the release that the user verified during installation. Cold specialist
loads also blocked the single Shell request loop, so clients timed out and a
broken response could stop the service.

## Decision

The installer persists the verified release manifest and the trusted Ed25519
public key. At startup, FAM Core re-verifies the manifest signature and every
component digest. The runtime catalog reads manifests, bindings, and model
policy from the signed expert archive, joins only exact package coordinates,
filters the result to configured runtime models, and binds each model to the
digest and size of its present Ollama manifest.

The product database stores enabled/disabled state for each signed expert. A
release synchronization may update package provenance but must preserve an
explicit disable. Only enabled entries reach selection.

Inference runs on per-task background workers. Shell snapshot requests return
durable progress immediately while cold imports, model loads, repair, or strong
escalation continue. SQLite query-and-fetch operations retain the database lock
for the full read so polling and workers cannot corrupt cursor observations.

## Consequences

- Unconfigured or unsigned archive bindings cannot become runtime candidates.
- Tampering with an activated component makes diagnosis and startup fail closed.
- The seven current runtime models have explicit signed package provenance and
  durable enablement state.
- Task workers must remain restart-safe and cannot use process memory as the
  authoritative lifecycle state.

