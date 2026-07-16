# ADR 0037: Use replay-safe declared edges for plan controls

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Bind cancellation, trusted-deadline timeout, and typed degradation to exact plan
instance/revision and routed context. Require existing `cancelled` or
`unavailable` edges, reserve control identity before compare-and-set, and persist
bounded reference-only control evidence. Keep terminal states absorbing and
provider-independent.

## Consequences

- Controls cannot invent fallback targets.
- Early timeouts are rejected.
- Stale or replayed controls cannot mutate state.
- Degradation remains visible and typed for later final-result policy.
- In-memory policy/replay state is not restart durable.

## Evidence

- `src/fam_os/core/lifecycle/control_contracts.py`
- `src/fam_os/core/lifecycle/control_service.py`
- `tests/unit/test_core_control_transitions.py`
- `docs/protocols/CORE_CONTROL_TRANSITIONS.md`
