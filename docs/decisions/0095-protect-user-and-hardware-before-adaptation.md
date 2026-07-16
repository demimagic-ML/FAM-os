# ADR 0095: Protect user workload and hardware before adaptation

- Status: accepted
- Date: 2026-07-16

## Decision

Battery, thermal, and foreground protections override speculation and background adaptation. Background learning is idle-only when unconstrained.
