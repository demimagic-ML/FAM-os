# Handoff 0036: Replay-safe plan control transitions

**Date:** 2026-07-16  
**Plan step:** Phase 4.7  
**Status:** Complete  
**Previous handoff:** `0035-core-attempt-transitions.md`

## Objective

Add cancellation, trusted deadline timeout, and typed degradation through only
reviewed plan edges, with replay protection and absorbing terminals.

## Scope completed

- Added typed control commands, results, deadline policy, and rejections.
- Added atomic control-ID replay protection.
- Required `cancelled` edges for cancellation and `unavailable` edges for timeout
  and degradation.
- Rejected early deadlines, stale revisions, missing edges, replay, and terminals.
- Persisted cancellation/timeout/degradation references without payload text.
- Bound degradation control identity to degradation evidence identity.
- Added provider-independent tests and architecture guard.

## Explicitly not completed

- Final `TaskResult` construction or release.
- Durable deadlines/replay/state.
- Provider cancellation signals or real degradation adapters.

## Architecture and decisions

ADR 0037 keeps control policy deterministic and provider-neutral. The reviewed
plan chooses the terminal/fallback target. Timeout reuses `unavailable` while its
typed evidence remains distinguishable. Control IDs losing a final state race
remain consumed.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/lifecycle/control_contracts.py` | Commands, deadline policy, result, and rejection vocabulary. |
| `src/fam_os/core/lifecycle/control_ports.py` | Deadline and replay ports. |
| `src/fam_os/core/lifecycle/control_registry.py` | In-memory policy and replay implementations. |
| `src/fam_os/core/lifecycle/control_service.py` | Validate and advance control transitions. |
| `src/fam_os/core/lifecycle/contracts.py` | Add bounded control evidence kinds. |
| `tests/unit/test_core_control_transitions.py` | Prove cancellation, timeout, degradation, replay, and edges. |
| `tests/architecture/test_core_control_boundary.py` | Prevent provider imports. |
| `docs/protocols/CORE_CONTROL_TRANSITIONS.md` | Document control semantics. |
| `docs/decisions/0037-replay-safe-plan-controls.md` | Record the durable decision. |
| `README.md`, `src/fam_os/core/README.md`, `MASTER_PLAN.md` | Update project status. |

## Public interfaces

- Added `ControlCommand`, `ControlKind`, `ControlRejection`,
  `ControlTransitionResult`, and `PlanDeadlinePolicy`.
- Added deadline/control replay ports and in-memory implementations.
- Added `PlanControlService.cancel`, `timeout`, and `degrade`.
- Added cancellation, timeout, and degradation evidence kinds.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_control_transitions tests.architecture.test_core_control_boundary
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
larry index . && larry health .
```

Result: 6 focused tests passed; full suite passed 391 tests; 35 schema artifacts
matched; compilation and AST size policy passed; Larry indexed 536 files and
1,478 symbols; graph contains 7,615 nodes and 25,370 edges; health is clean.

## Evidence and artifacts

- `docs/protocols/CORE_CONTROL_TRANSITIONS.md`
- `docs/decisions/0037-replay-safe-plan-controls.md`
- `tests/unit/test_core_control_transitions.py`

## Known limitations and risks

- State is in-memory and lost on restart.
- Timeout uses `unavailable`; evidence kind carries the precise cause.
- No provider cancellation signal is sent in this fake-driven phase.

## Operational notes

No services, models, applications, or machine configuration changed.

## Recommended next entry point

Begin Phase 4.8. Build final results only from terminal snapshots. Release only
from `RELEASE`, require accepted trusted evidence where verification is required,
and map withhold/fail/cancel/timeout/degradation to content-free safe results.
