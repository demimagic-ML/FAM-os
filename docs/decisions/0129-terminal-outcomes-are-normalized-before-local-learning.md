# ADR 0129: Terminal outcomes are normalized before local learning

**Status:** Accepted  
**Date:** 2026-07-17

## Context

Phase 11 defined useful local frequency, context, escalation, prefetch, and drift
algorithms, but no installed production path supplied their observations. The
durable Core retained request prompts, verifier declarations, candidate text,
and verifier feedback after completion. Copying any of that working material
into an adaptation dataset would create a second, less controlled memory system.
Deleting it immediately would also break repeated result reads, exact-citation
presentation, restart recovery, and deterministic undo.

## Decision

Production terminalization first assembles and presents the final `TaskResult`,
then persists that user-visible result as an owner-encrypted terminal record. In
the same SQLite transaction it normalizes the completed working state: request
prompts, nested application request prompts, action summaries, candidate text,
and verifier feedback become one fixed redaction marker, and the now-unneeded
verification declaration is removed. Verifier status, package provenance,
digest facts, acceptance evidence, action results, citations, and the final
user-visible result remain available.

Only an outcome whose inference assurance, final status, result assurance, and
terminal disposition are all verified release states may create a learning
record. It must bind exactly one passing acceptance record to exactly one
released candidate. Unverified, grounded-only, failed, cancelled, denied, and
withheld results are normalized but never learned.

The learning record contains only a closed intent workflow bucket, selected
expert identity and tier, a power-of-two context-token bucket, whether escalation
occurred, timestamp, evidence identities, and a digest of safe evidence metadata.
It has structural invariants that raw prompts, candidate content, source content,
and application payloads are absent. Records are local-only and owner-encrypted.
They do not carry authority and cannot weaken routing, permissions, verification,
or acceptance.

Terminal result insertion, optional verified-learning insertion, and working
content normalization are atomic. The request identity is the terminal-result
idempotency key and acceptance identity is unique per owner learning record.
Background completion performs finalization even if a client stops polling;
concurrent projections return the single stored result. Restart reads that
stored result without rerunning inference or reconstructing redacted evidence.

## Consequences

- Installed adaptation receives no observation from an unverified outcome.
- The final answer and exact citations remain available after restart while
  duplicated prompt and candidate working copies do not.
- Detailed verifier feedback is available during repair but is normalized after
  terminalization; stable verifier facts and provenance remain.
- Coarse context buckets reduce prompt-length fingerprinting while remaining
  useful for conservative context planning.
- Phase 20.6 must consume these records through bounded deterministic predictors;
  this decision does not activate prediction or prefetch by itself.
- Phase 20.7 remains responsible for visible inspection, disable, reset, drift,
  and rollback controls.
