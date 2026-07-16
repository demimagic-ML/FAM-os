# Handoff 0032: Deterministic Core execution-plan state machine

**Date:** 2026-07-16  
**Plan step:** Phase 4.3  
**Status:** Complete  
**Previous handoff:** `0031-core-routing-lifecycle.md`

## Objective

Execute the transition semantics of an immutable `ExecutionPlan` without
invoking providers, while binding the plan to routed authority and preventing
illegal, stale, concurrent, repeated, or post-terminal transitions.

## Scope completed

- Added exact request, complete route, and ordered capability binding at start.
- Added immutable plan snapshots and append-only lifecycle events.
- Added full event-log replay validation against the immutable plan.
- Added atomic in-memory create and compare-and-set replacement.
- Added declared-edge-only outcome transitions and typed rejections.
- Made release, withhold, and fail terminal dispositions absorbing.
- Added a concurrency test proving only one same-revision report can win.
- Added an architecture guard against provider and external-boundary imports.

## Explicitly not completed

- Observation acquisition or action proposal/execution.
- Permission rechecks after routing.
- Approval, repair budgets, cancellation, timeout, or degradation.
- Final `TaskResult` construction.
- Durable state across process restart.

## Architecture and decisions

ADR 0033 selects an optimistic evented state machine. Persistence owns atomicity
behind `PlanStateRepository`; Core policy owns plan binding and edge selection.
Snapshots deliberately exclude the admitted request, prompt, principal, session,
authority, and provider sessions. Every state can be reconstructed from revision
zero plus declared plan transitions.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/lifecycle/contracts.py` | Define events, snapshots, typed rejections, and replay invariants. |
| `src/fam_os/core/lifecycle/ports.py` | Define the replaceable plan-state repository boundary. |
| `src/fam_os/core/lifecycle/repository.py` | Provide locked in-memory create/get/compare-and-set persistence. |
| `src/fam_os/core/lifecycle/service.py` | Bind, start, and deterministically advance plans. |
| `src/fam_os/core/lifecycle/__init__.py` | Export the lifecycle public surface. |
| `tests/unit/test_core_plan_lifecycle.py` | Prove binding, branching, persistence, concurrency, and rejection behavior. |
| `tests/architecture/test_core_plan_lifecycle_boundary.py` | Prevent provider/runtime/external imports. |
| `docs/protocols/CORE_PLAN_LIFECYCLE.md` | Document binding, state, events, transitions, and limits. |
| `docs/decisions/0033-optimistic-evented-plan-state-machine.md` | Record the durable state-machine decision. |
| `docs/protocols/CORE_CONTRACTS.md` | Link the plan contract to its generic runtime. |
| `src/fam_os/core/README.md` | Record lifecycle ownership. |
| `README.md` | Update current implementation status. |
| `MASTER_PLAN.md` | Complete Phase 4.3 and select Phase 4.4. |

## Public interfaces

- Added `PlanLifecycleEvent`, `PlanInstanceSnapshot`, `PlanEventKind`, and
  `PlanRejection`.
- Added `PlanStartResult` and `PlanAdvanceResult` one-of results.
- Added `PlanStateRepository` with `create`, `get`, and optimistic `replace`.
- Added `InMemoryPlanStateRepository`.
- Added `PlanLifecycleService.start` and `PlanLifecycleService.advance`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_plan_lifecycle tests.architecture.test_core_plan_lifecycle_boundary tests.unit.test_core_plan_contracts
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
# Parse src/ and tools/ with ast; fail for modules >=300 or functions >=50 lines.
larry index .
larry health .
```

Result: 16 focused tests passed; the full suite passed 360 tests; all 35 schema
artifacts matched; compilation passed; the AST size policy was clean; Larry
indexed 501 files and 1,344 symbols with clean freshness/verification; the
persisted code graph contains 7,291 nodes and 23,055 edges.

## Evidence and artifacts

- `docs/protocols/CORE_PLAN_LIFECYCLE.md`
- `docs/decisions/0033-optimistic-evented-plan-state-machine.md`
- `tests/unit/test_core_plan_lifecycle.py`
- `tests/architecture/test_core_plan_lifecycle_boundary.py`

## Known limitations and risks

- State is process-local and disappears on restart.
- The state machine currently trusts its caller to supply a typed outcome; later
  steps must bind that outcome to authorized evidence.
- Permission expiry is not yet rechecked on lifecycle transitions.
- A plan remains immutable; bounded retries must be unrolled into distinct steps.

## Operational notes

No services, models, ports, machine configuration, or credentials changed.

## Recommended next entry point

Begin Phase 4.4 in `core/lifecycle`. Read the Application Fabric observation,
action, and permission contracts plus ADR 0033. Add fake provider ports and
typed evidence references for `OBSERVE` and `PREPARE_ACTION` only. Recheck
permission validity and exact current-step capability scope before provider
access. Do not execute an action or treat observation authority as modification
authority.
