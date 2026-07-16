# ADR 0088: Memory relevance never widens scope

- Status: accepted
- Date: 2026-07-16

## Decision

Memory candidates must pass exact scope before freshness, relevance, and volume decisions. Relevance scores cannot compensate for scope denial. Context assembly uses a hard token budget and deterministic ordering; overflow is rejected with evidence.

## Consequences

- Highly relevant cross-user or cross-workspace memory remains inaccessible.
- Stale and low-value records do not consume inference context.
- Context size is predictable and scheduler-compatible.
- Rejection reasons are inspectable rather than hidden in model prompts.
