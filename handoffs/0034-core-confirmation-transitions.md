# Handoff 0034: Replay-safe confirmation and permission-expiry transitions

**Date:** 2026-07-16  
**Plan step:** Phase 4.5  
**Status:** Complete  
**Previous handoff:** `0033-core-authorized-application-steps.md`

## Objective

Record action approval, denial, and permission expiry as explicit immutable plan
transitions while binding user intent to exactly one proposal, grant, principal,
plan revision, and reviewed edge without executing the action.

## Scope completed

- Added `expired` to the Core plan outcome vocabulary and strict schema artifact.
- Added permission-grant identity to bounded plan evidence references.
- Added typed confirmation and permission-expiry commands/results.
- Bound decisions to current `CONFIRM_ACTION`, latest proposal reference,
  capability, grant, admitted principal, proposal time, route, and revision.
- Rechecked original Core expiry and authoritative Application grant activity.
- Added explicit approved, denied, and expired transition paths.
- Added atomic confirmation replay protection across plan instances.
- Added a no-provider/no-action-execution architecture guard.

## Explicitly not completed

- Application action execution or modification authority.
- Precondition/postcondition verification or reversal.
- Durable user-presence authentication, confirmation, or plan storage.
- Repair/escalation, cancellation/timeout, degradation, or final-result policy.

## Architecture and decisions

ADR 0035 makes permission expiry distinct from explicit denial and selects
cross-plan replay protection. Confirmation IDs are reserved after deterministic
validation and edge checks but before plan compare-and-set. A lost final race
consumes the confirmation, preferring non-replay over silent reuse. Confirmation
state remains independent from provider execution.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/contracts/plan.py` | Add the explicit `expired` transition outcome. |
| `schemas/v1alpha1/fam.core.execution-plan.schema.json` | Regenerate the strict enum artifact. |
| `src/fam_os/core/lifecycle/confirmation_contracts.py` | Define confirmation/expiry commands, dispositions, rejections, and results. |
| `src/fam_os/core/lifecycle/confirmation_ports.py` | Define atomic replay reservation. |
| `src/fam_os/core/lifecycle/confirmation_registry.py` | Provide locked in-memory replay protection. |
| `src/fam_os/core/lifecycle/confirmation_service.py` | Validate, replay-protect, and advance confirmation/expiry states. |
| `src/fam_os/core/lifecycle/contracts.py` | Extend evidence kinds and grant binding. |
| `src/fam_os/core/lifecycle/application_service.py` | Persist grant identity with application evidence references. |
| `src/fam_os/core/lifecycle/__init__.py` | Export the confirmation lifecycle surface. |
| `tests/unit/test_core_confirmation_transitions.py` | Prove binding, expiry, denial, replay, and staleness behavior. |
| `tests/architecture/test_core_confirmation_boundary.py` | Prevent provider/action-execution dependencies. |
| `tests/unit/test_core_application_steps.py` | Add explicit confirmation expiry edge to the fake plan. |
| `docs/protocols/CORE_CONFIRMATION_TRANSITIONS.md` | Document confirmation and expiry semantics. |
| `docs/protocols/CORE_CONTRACTS.md` | Document `expired`. |
| `docs/decisions/0035-explicit-replay-safe-confirmation-transitions.md` | Record the durable confirmation decision. |
| `src/fam_os/core/README.md` | Update Core ownership. |
| `README.md` | Update implementation status. |
| `MASTER_PLAN.md` | Complete Phase 4.5 and select Phase 4.6. |

## Public interfaces

- Added `StepOutcome.EXPIRED`.
- Added `PlanEvidenceKind.ACTION_CONFIRMATION` and
  `PlanEvidenceKind.PERMISSION_EXPIRY`.
- Extended `PlanEvidenceReference` with `permission_grant_id`.
- Added `ConfirmationCommand`, `PermissionExpiryCommand`,
  `ConfirmationDisposition`, `ConfirmationRejection`, and
  `ConfirmationTransitionResult`.
- Added `ConfirmationReplayRegistry` and
  `InMemoryConfirmationReplayRegistry`.
- Added `ConfirmationTransitionService.record_confirmation` and
  `record_permission_expiry`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_core_confirmation_transitions tests.architecture.test_core_confirmation_boundary
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
# Parse src/ and tools/ with ast; fail for modules >=300 or functions >=50 lines.
larry index .
larry health .
```

Result: 9 focused tests passed; the full suite passed 379 tests; all 35 schema
artifacts matched; compilation passed; the AST size policy was clean; Larry
indexed 518 files and 1,417 symbols with clean freshness/verification; the
persisted code graph contains 7,467 nodes and 24,375 edges.

## Evidence and artifacts

- `docs/protocols/CORE_CONFIRMATION_TRANSITIONS.md`
- `docs/decisions/0035-explicit-replay-safe-confirmation-transitions.md`
- `schemas/v1alpha1/fam.core.execution-plan.schema.json`
- `tests/unit/test_core_confirmation_transitions.py`
- `tests/architecture/test_core_confirmation_boundary.py`

## Known limitations and risks

- Replay and plan state are process-local and reset on restart.
- A confirmation that loses a post-reservation compare-and-set race is consumed;
  a fresh confirmation is required.
- Trusted user-presence authentication is not yet implemented.
- Approval is only state evidence and cannot execute an application action.

## Operational notes

No application, model, service, port, machine setting, or credential changed.
One generated schema artifact was updated through the canonical renderer.

## Recommended next entry point

Begin Phase 4.6 in `core/lifecycle`. Add immutable attempt identity and bounded
repair/escalation counters or budgets bound to plan state. Only distinct unrolled
repair/inference/verification steps may consume a repair or escalation. Reserve
attempt identities and budgets atomically before transition, retain failed
attempt references, and never release a failed candidate.
