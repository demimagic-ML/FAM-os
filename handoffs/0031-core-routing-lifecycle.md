# Handoff 0031: Permission-preserving Core routing lifecycle

**Date:** 2026-07-16  
**Plan step:** Phase 4.2  
**Status:** Complete  
**Previous handoff:** `0030-core-request-admission.md`

## Objective

Add the provider-neutral FAM Core routing boundary after trusted request
admission without disclosing identity or allowing routing to alter effective
permission scope.

## Scope completed

- Added a Core routing service that accepts only `AdmittedTaskRequest`.
- Rechecked permission expiry immediately before routing.
- Sent only request ID, prompt, and effective capabilities to `TaskRouter`.
- Bound valid route evidence to the admitted request in `RoutedTaskRequest`.
- Required exact ordered capability equality across admission and routing.
- Mapped unavailable providers and invalid evidence to fixed structured errors.
- Tightened routing version, identifier, prompt, capability, confidence, and
  reason validation.
- Added unit and architecture tests covering the lifecycle and dependency
  boundary.

## Explicitly not completed

- Execution-plan construction or execution.
- Retry/backoff orchestration.
- Persisted lifecycle events.
- Real model, expert, application, verifier, or desktop invocation.

## Architecture and decisions

ADR 0032 establishes that classification is not authority: routing may choose a
route but must preserve the admitted effective capability tuple exactly. Core
constructs the least-data routing request and keeps runtime/model implementations
behind the existing `TaskRouter` port. Provider exceptions never cross into Core
failure evidence.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/routing/contracts.py` | Bind admitted requests to valid route evidence and define one-of outcomes. |
| `src/fam_os/core/routing/service.py` | Enforce expiry, least-data routing, exact permission preservation, and safe failures. |
| `src/fam_os/core/routing/__init__.py` | Export the Core routing public surface. |
| `src/fam_os/routing/contracts.py` | Harden routing contract validation. |
| `tests/unit/test_core_routing_lifecycle.py` | Prove routing lifecycle behavior and adversarial rejection. |
| `tests/architecture/test_core_routing_boundary.py` | Prevent runtime and external-boundary imports. |
| `docs/protocols/CORE_ROUTING_LIFECYCLE.md` | Document lifecycle, privacy, binding, and failure invariants. |
| `docs/protocols/CORE_CONTRACTS.md` | Link the Core contract family to the implemented lifecycle. |
| `docs/decisions/0032-permission-preserving-core-routing.md` | Record the durable routing boundary decision. |
| `src/fam_os/core/README.md` | Record Core ownership and current implementation state. |
| `README.md` | Update project status. |
| `MASTER_PLAN.md` | Complete Phase 4.2 and select Phase 4.3. |

## Public interfaces

- Added `RoutedTaskRequest`.
- Added `CoreRoutingOutcome`.
- Added `CoreRoutingService.route(admitted)`.
- Strengthened construction invariants for existing `RoutingRequest`,
  `RouteDecision`, and `RoutingResult` contracts without changing their current
  contract version.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_routing_lifecycle tests.architecture.test_core_routing_boundary tests.unit.test_routing_contracts
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
# Parse src/ and tools/ with ast; fail for modules >=300 or functions >=50 lines.
```

Result: 12 focused tests passed; the full suite passed 351 tests; all 35 schema
artifacts passed compatibility validation; compilation passed; and the source
size/AST policy reported no implementation module at or above 300 lines and no
function at or above 50 lines.

## Evidence and artifacts

- `docs/protocols/CORE_ROUTING_LIFECYCLE.md`
- `docs/decisions/0032-permission-preserving-core-routing.md`
- `tests/unit/test_core_routing_lifecycle.py`
- `tests/architecture/test_core_routing_boundary.py`

## Known limitations and risks

- An injected router can be model-backed; this lifecycle validates its evidence
  but does not evaluate route quality.
- Permission expiry is not yet a persisted plan event.
- Retry policy is expressed in failure evidence but not yet executed.
- These lifecycle types remain in-process Python contracts until a transport
  boundary requires serialization.

## Operational notes

No services, models, ports, credentials, or machine configuration changed.

## Recommended next entry point

Begin Phase 4.3. Read `src/fam_os/core/contracts/plan.py`, the plan-contract
tests, this handoff, and ADR 0032. Implement a deterministic persisted in-memory
state machine that starts only from a route bound to the same request and exact
capability tuple, rejects stale or repeated transitions, and stops at a terminal
release, withhold, or fail step without invoking real providers.
