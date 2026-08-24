# ADR 0137: Remote loss consumes budget before unchanged local retry

**Status:** Accepted  
**Date:** 2026-07-17  
**Extends:** ADR 0136

## Context

A remote request can be processed by the peer even when the requester receives
no result. Retrying the peer would risk duplicate work; forgetting the first
reservation would undercount global cost; blindly switching to a local model
could use changed authority, verifier, or task acceptance. Process loss can also
occur after the complete candidate transaction but before the inference record
advances.

## Decision

Before opening the remote socket, Core calculates a canonical SHA-256 binding of
the durable request, current active request authority, immutable execution plan,
remote route, and verifier declaration. The remote `AttemptBudgetReservation`
stores that digest and remote-plan identity. Core persists
`remote_attempt_consumed=true` before calling the remote executor.

On restart or a classified failure, Core never re-sends that remote attempt. It
recomputes the acceptance digest and permits local recovery only when the digest
is unchanged, authority remains active, the failure is disconnect, timeout,
partial result, uncertain completion, or authenticated provider failure, a local
model is admissible, and the shared global budget accepts one distinct
`local_recovery` reservation. Policy change, authentication failure, invalid
result, changed digest, unavailable model, or exhausted budget fails closed.

The retry receives only the original locally available prepared input; remote
fragments are discarded and never become repair feedback. Its candidate enters
the same verifier and final-result policy. `RemoteRecoveryEvidence` is encrypted
and content-free and binds failure class, both acceptance digests, remote/local
reservations, local selection, local candidate, and disposition. The final
release must reference a matching recovered record.

Restart reconciliation recognizes a pending complete remote candidate or a
completed recovered local candidate from their atomic evidence transactions and
advances the inference record without re-running either model. A pending local
recovery may resume the side-effect-free local inference under its existing
reservation.

## Consequences

- A started remote attempt is never free and is never replayed after uncertain
  completion.
- Local fallback is a separately visible bounded attempt, not an implicit model
  substitution.
- Changed authority, acceptance, verifier, or signed-result trust cannot be
  hidden by a local retry.
- Console exposes content-free recovery state while prompts and partial results
  remain absent from recovery evidence and SQLite.
- The signed exit proof remains same-host. Phase 21.7 requires the same behavior
  across at least two physical Linux machines.
