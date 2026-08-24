# Handoff 0233: Receipt-driven master lifecycle driver

**Date:** 2026-07-19  
**Plan step:** Phase 30.1 and 30.9  
**Status:** Partial  
**Previous handoff:** `0232-generated-content-review-and-incident-governance.md`

## Objective

Create the trusted Core boundary that advances the installed master loop only
after real engineering services return exact typed receipts.

## Scope completed

- Added a typed driver for repository analysis, architecture, candidate
  creation, verification, changeset checkpoint, apply, reverification, commit,
  publication approval/publication, rollback, and completion.
- Bound every transition to the current task, candidate, checkpoint, action, or
  approval identity as applicable.
- Derived command/file budget consumption from receipts.
- Revalidated the active task grant before every transition.
- Removed raw stage/evidence advancement from the product API.
- Proved a complete typed apply/commit/draft-publication lifecycle and hostile
  failed/mismatched evidence rejection.
- Proved product-level grant revocation blocks the driver without changing task
  state.

## Explicitly not completed

- The active planner/executor that calls each concrete service to obtain these
  typed inputs.
- Dependency, design, documentation, review, incident, database, environment,
  deployment, and release receipt attachment to the main loop.
- Installed signed-artifact end-to-end qualification.

## Architecture and decisions

ADR 0200 makes typed receipts and repeat grant validation the only product
transition boundary. ADR 0198 continues to forbid raw client advancement.

## Public interfaces

`EngineeringLifecycleDriver` and `MasterEngineeringLoop.state`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_engineering_lifecycle_driver \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_master_engineering_loop -v
```

Result: seven tests passed, including full receipt-driven publication, failed
evidence rejection, restart persistence, budget bounds, and grant revocation.

## Known limitations and risks

- The driver records receipt identities; the responsible typed services retain
  the receipt bodies.
- Time and byte accounting still needs direct runtime aggregation when the
  active executor is composed.
- Publication byte accounting comes from the network broker and is not yet
  attached by the driver.

## Recommended next entry point

Implement the active Core engineering orchestrator for repository observation,
planning, candidate creation, signed tool execution, repair, and checkpoint
presentation, using this driver after each real service result.
