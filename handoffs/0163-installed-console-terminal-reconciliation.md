# Handoff 0163: Installed Console terminal reconciliation

**Date:** 2026-07-17  
**Plan step:** Phase 23.3, 23.6, and 23.8 readiness  
**Status:** Partial; the reported livelock is fixed and installed, final Phase 23 gates remain open  
**Previous handoff:** `0162-installed-console-terminal-and-scoped-observation.md`

## Objective

Correct the owner-reported browser task that continued animating
`Finalizing durable evidence` after its first VS Code observation had failed.

## Confirmed failure

The production database proved this was not merely a visual delay. Request
`f0d38fbf-ff14-4e5a-9050-e1fac18b88ae` committed its terminal plan at
`2026-07-17T16:43:05.069Z`, but its inference execution did not become terminal
until `2026-07-17T18:15:29.986Z`. The Console therefore had a durable plan /
execution mismatch for about 92 minutes and truthfully rendered the unfinished
state shown by the owner.

## Implementation

- `terminal_reconciliation.py` now owns the narrow fail-closed invariant for a
  terminal plan whose inference execution is still unfinished.
- `ProductionTaskGateway.snapshot()` waits for the worker that owns terminal
  evidence, then atomically reconciles the execution if that worker stopped
  without closing the durable state.
- Reconciliation is idempotent under a concurrent terminal commit and never
  converts a non-terminal plan into a result.
- The Console keeps SSE for low-latency updates but also starts a two-second
  status watchdog. A live-looking but silent event stream can no longer leave
  the page blinking forever.

## Validation

Focused Core, application-fabric, and Console HTTP validation passed 31 tests.
The set includes connector disconnect, connector timeout, failed observation
evidence, terminal-plan reconciliation, restart retention, SSE, and Console
task behavior. Ruff, strict Mypy for the new reconciliation boundary, and Node
JavaScript syntax validation passed.

Signed release `fam-os-current-test-20260717-11` is installed and diagnoses
healthy. Source and installed hashes match for both the gateway and browser
asset. The signed manifest SHA-256 is
`75fd622a8579359a91f7850516fe1af35ebb89189d113f9d9eefe953d4dda3ea`;
the temporary private release key was removed.

Two post-install physical requests exercised both sides of the failure:

- `adccabc8-a2be-4c1c-bcf1-2470b477e129` deliberately targeted a non-active
  document. It reached an owner-visible terminal withheld result in under one
  second instead of remaining on `Finalizing`.
- `e80f33b3-f29d-4e05-8087-787589de7816` repeated `What is in this project?`
  against the live VS Code context. Diagnostics, active editor, selection,
  inference, and release all succeeded; the task completed with grounded
  assurance in eight seconds.

## Files changed

- `src/fam_os/core/production/terminal_reconciliation.py`
- `src/fam_os/core/production/gateway.py`
- `src/fam_os/console/static/app.js`
- `tests/unit/test_production_task_gateway.py`
- `MASTER_PLAN.md`

## Remaining gaps

This closes the terminal-display livelock. It does not make an active-editor
observation equivalent to whole-workspace analysis. Phase 23 still needs an
explicit workspace surface, approved recursive repository tooling, clean
installed matrices, soak, rollback, recovery, security review, and removal.
Phase 22 specialist promotion also remains independently open.
