# ADR 0086: Ephemeral memory fails closed at capacity

- Status: accepted
- Date: 2026-07-16

## Decision

Session and working memory use a bounded in-process store with exact scope checks and content-digest verification. Capacity overflow raises an error rather than evicting an unrelated record. Expired records are never returned. Deletion receipts are emitted only after byte removal.

## Consequences

- Tasks do not lose context through hidden cross-session eviction.
- Callers must deliberately purge expiry or request a larger admitted budget.
- Ephemeral process loss is expected and distinct from persistent document memory.
- Scope checks are reusable by later persistent stores and retrieval gates.
