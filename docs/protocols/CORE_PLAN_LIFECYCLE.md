# Core execution-plan lifecycle

## Invariant

Only an exactly route-bound immutable `ExecutionPlan` may start. Once started,
the current step advances through one declared `(source step, outcome)` edge at
most once. A release, withhold, or fail step is terminal.

```text
RoutedTaskRequest + exactly bound ExecutionPlan
  -> revision 0 / started event / entry step
  -> compare expected revision
  -> select the one declared outcome edge
  -> atomic compare-and-set snapshot plus transition event
  -> next active step or terminal disposition
```

## Binding and retained data

`PlanLifecycleService.start` requires exact equality for:

- request identity between the admitted route and plan;
- the complete route decision between routing evidence and plan;
- the ordered effective capability tuple across permission, route, and plan.

The persisted snapshot retains the immutable plan, instance identity, current
step, revision, terminal disposition, append-only lifecycle events, and an opaque
admission ID plus the original permission expiry. The latter prevents stale
permission replacement during later rechecks. It does not retain the admitted
request, prompt, principal, session, authority record, model, connector,
application session, or credentials.

## Deterministic transition rule

An advance supplies an instance ID, expected revision, and typed `StepOutcome`.
The state machine searches only transitions declared by the immutable plan. A
missing edge is rejected as `illegal_outcome`; it never guesses a fallback.

Every successful transition increments the revision once and appends one event.
The in-memory repository replaces state only when the stored revision equals the
caller's expected revision. Concurrent, stale, and repeated reports therefore
cannot both advance the same step.

## Event-log integrity

Every snapshot validates its complete event history:

- revision zero is one `started` event targeting the plan entry;
- event IDs are unique;
- event revisions and sources are contiguous;
- every recorded outcome selects the recorded target in the plan;
- each event's terminal disposition matches its target step;
- the final event target equals the snapshot's current step;
- the snapshot terminal disposition equals its current step.

This is internal in-memory persistence, not a durable audit log. Durable recovery
and authenticated external storage remain productization work.

## Rejections

- `invalid_binding`: plan and routed evidence differ;
- `already_started`: the same request/plan binding or instance already exists;
- `not_found`: no such instance exists;
- `revision_conflict`: the caller reports against stale state or lost a race;
- `terminal`: a terminal plan cannot advance;
- `illegal_outcome`: the current step has no matching declared edge.

Expected lifecycle conflicts are typed result values, not provider exceptions.

## Dependency boundary

The state machine depends only on Core contracts, Core routed evidence, and its
repository port. It does not invoke experts, models, applications, connectors,
verifiers, schedulers, Supervisor, memory, OS adapters, or desktop automation.
Those providers will produce typed evidence for later lifecycle steps.

## Current limitations

- State is process-local and lost on restart.
- Phase 4.3 consumes a typed outcome but does not acquire observations or execute
  work.
- Application-backed observation and proposal transitions recheck the original
  admission expiry; generic non-provider transitions do not yet do so.
- Approval, repair budgets, cancellation, timeout, degradation, and final-result
  assembly remain later Phase 4 steps.
