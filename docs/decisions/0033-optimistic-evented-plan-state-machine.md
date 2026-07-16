# ADR 0033: Use an optimistic evented state machine for execution plans

**Status:** Accepted  
**Date:** 2026-07-16

## Context

`ExecutionPlan` already defines an immutable acyclic graph, but Core previously
had no generic runtime state for its current step. A state machine must not start
from an unrelated route, choose undeclared fallback edges, process the same step
twice, or continue after a terminal disposition. It must also remain independent
of concrete experts, applications, and runtimes.

## Decision

Create `core.lifecycle` with immutable plan snapshots and append-only lifecycle
events behind a `PlanStateRepository` port. Start only when request identity,
complete route decision, and ordered effective capabilities exactly match the
routed request.

Use integer revisions and atomic compare-and-set replacement. Each accepted
typed outcome follows exactly one transition declared by the plan, increments
the revision once, and appends one replay-valid event. Reject missing, stale,
repeated, illegal, and terminal transitions with typed rejection values.

Provide a locked in-memory repository for Phase 4 fake-driven tests. Persist only
plan lifecycle evidence, not prompt, identity, authority, or provider sessions.

## Consequences

- Concurrent outcome reports cannot both advance one step.
- Event history can reconstruct and validate every accepted transition.
- Plans cannot be substituted across requests or routes.
- Terminal release, withhold, and fail states are absorbing.
- Later providers can feed typed outcomes without entering lifecycle policy.
- Process restart currently loses state; durable recovery requires a later
  repository adapter and storage decision.

## Alternatives considered

1. Keep only a mutable current-step field: rejected because it loses transition
   history and weakens recovery evidence.
2. Use a global lock around the entire Core service: rejected because persistence
   owns atomicity and must remain replaceable.
3. Let provider callbacks choose the next step: rejected because providers are
   untrusted evidence producers, not lifecycle policy.
4. Automatically fall back when an edge is missing: rejected because it invents
   behavior outside the reviewed plan.
5. Persist the full admitted request: rejected because identity, prompt, and
   authority are unnecessary for plan transition state.

## Evidence

- `src/fam_os/core/lifecycle/`
- `tests/unit/test_core_plan_lifecycle.py`
- `tests/architecture/test_core_plan_lifecycle_boundary.py`
- `docs/protocols/CORE_PLAN_LIFECYCLE.md`
