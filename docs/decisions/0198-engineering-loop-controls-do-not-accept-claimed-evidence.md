# ADR 0198: Engineering loop controls do not accept claimed evidence

Status: Accepted

## Context

The persistent master engineering loop previously existed only as a component.
Making it reachable from the installed Console and Shell creates a new trust
boundary: a local client must not be able to mark inspection, verification,
workspace mutation, Git publication, or rollback complete merely by supplying
an arbitrary evidence identifier.

## Decision

The installed product composes one owner-scoped `ProductEngineeringLoopApi`
over a dedicated optimistic SQLite store. Authenticated Console and same-owner
Unix Shell clients may start a task under an active, reconfirmed, exact
task-scoped grant; list and inspect projections; and resume after restart.

External clients do not receive a generic stage-advance operation. Stage
advancement and auxiliary evidence recording remain Core-side operations and
must eventually be called only by the master coordinator after the responsible
repository, workspace, verifier, dependency, design, Git, deployment, or
rollback service returns its typed receipt. Each Core-side transition also
rechecks that the exact task grant remains active and usable.

Restart resume may clear pending checkpoint authority without an active grant,
because forgetting authority is a safe reduction. It cannot perform an effect.

## Consequences

- Lifecycle state and budgets are reachable from the real installed service.
- A Console or Shell caller cannot manufacture success by naming an evidence ID.
- Revoked, expired, mismatched, or restart-unconfirmed grants cannot advance a
  task through the product facade.
- Phase 30.1 and 30.9 remain open until the receipt-driven coordinator invokes
  the actual engineering services end to end.

## Evidence

- `src/fam_os/product/engineering_loop_api.py`
- `src/fam_os/product/composition/engineering_loop.py`
- `src/fam_os/console/engineering_loop_routes.py`
- `src/fam_os/shell/engineering_loop_contracts.py`
- `src/fam_os/adapters/shell/engineering_loop_dispatch.py`
- `tests/integration/test_product_service_storage_modes.py`
- `tests/integration/test_console_engineering_loop.py`
- `tests/unit/test_fam_shell_engineering_loop_transport.py`

## Superseded decisions

None. This narrows the production exposure of ADR 0173.
