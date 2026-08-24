# ADR 0115: Restart never replays mutation authority

Status: Accepted

## Context

A daemon can stop after approval, during provider invocation, or after an action
occurred but before its terminal evidence committed. Reusing confirmation or
blindly invoking the provider again can duplicate an irreversible mutation.

## Decision

Restart discards prior confirmation for every nonterminal mutation. Prepared,
waiting, and approved actions return to `awaiting_approval`. Invoking, uncertain,
and reconciliation-required actions run only their declared postcondition
reconciler. They never receive provider retry authority. Inconclusive checks stay
`reconciliation_required`; verified checks can close the action without replay.

Read-only and inference requests may be marked safe to resume, but restart never
retains request authority. Mutation requests require fresh approval. All action
and request recovery states and decisions are durable versioned contracts.

## Consequences

- Restart may inconvenience the user with another approval, but cannot silently
  reuse old authority.
- Postcondition reconciliation must be deterministic and side-effect-free.
- A crash during reconciliation safely repeats observation, never mutation.
- Phase 18 task composition must persist recovery classification before work.

## Evidence

- `src/fam_os/product/restart_recovery.py`
- `src/fam_os/product/request_recovery.py`
- `tests/unit/test_restart_action_reconciliation.py`
