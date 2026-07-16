# ADR 0036: Bound repair and escalation with unrolled plan steps

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Repair and escalation can become unbounded retry loops or allow a provider to
choose its own authority. Failed candidates must remain available as evidence
without becoming releasable content, and attempt identities must not be replayed
across plans.

## Decision

Classify distinct unrolled inference-step IDs in a trusted per-plan
`AttemptBudgetPolicy`. Permit transition only through the current plan's declared
`failed` edge, with exact admitted capability scope. Count accepted event
references against configured repair/escalation ceilings and use plan
compare-and-set as atomic budget consumption.

Reserve failed and next-attempt IDs together through an atomic cross-plan replay
registry. Persist reference IDs, kinds, and capability only. Also strengthen
`ExecutionPlan` so planned capabilities exactly equal routed capabilities.

## Consequences

- Retry count is structurally finite and may be restricted further by policy.
- Providers cannot invent repair/escalation targets.
- Concurrent transitions cannot overspend a plan revision.
- Failed candidate content is never stored or released by attempt policy.
- Lost-race attempt IDs are consumed and must be replaced.
- Real expert invocation remains separate from lifecycle policy.

## Alternatives considered

1. Runtime loops: rejected because bounds and review become implicit.
2. Provider-selected retry targets: rejected because model output is untrusted.
3. Counters without event references: rejected because accepted consumption
   would lack reconstructable evidence.
4. Allow extra plan capabilities: rejected as authority widening.

## Evidence

- `src/fam_os/core/lifecycle/attempt_contracts.py`
- `src/fam_os/core/lifecycle/attempt_ports.py`
- `src/fam_os/core/lifecycle/attempt_registry.py`
- `src/fam_os/core/lifecycle/attempt_service.py`
- `tests/unit/test_core_attempt_transitions.py`
- `docs/protocols/CORE_ATTEMPT_TRANSITIONS.md`
