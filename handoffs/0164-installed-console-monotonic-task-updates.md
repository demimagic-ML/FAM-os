# Handoff 0164: Installed Console monotonic task updates

**Date:** 2026-07-17  
**Plan step:** Phase 23.3 and 23.6 readiness  
**Status:** Partial; the owner-reported stale browser state is fixed and installed  
**Previous handoff:** `0163-installed-console-terminal-reconciliation.md`

## Objective

Correct the browser Console that continued blinking on `Fail safely` even
though the durable plan, inference execution, and application execution had
already reached terminal state.

## Confirmed failure

The reported task was not stuck in Core. The production SQLite database showed
its three execution records were terminal, and a fresh authenticated task GET
returned the terminal snapshot in 11 milliseconds. The browser could still
display the older active snapshot because task state arrived over two
concurrent paths: SSE and the two-second authoritative HTTP watchdog.

The race was terminal HTTP update, watcher shutdown, then delivery of an
already-queued SSE update. Application tasks can project the active and
terminal states at the same Shell revision, so revision comparison alone would
not close the race. The stale event replaced the terminal state after all
watchers had stopped, leaving the page permanently stale.

## Implementation

- `task_updates.js` is a small browser/Node-compatible monotonic update policy.
- Updates for another task and updates below the current revision are rejected.
- Once a task is terminal, a nonterminal update can never replace it, including
  an update at the same revision.
- `app.js` applies this policy before mutating or rendering task state.
- The loopback server and Console page ship the new policy as a separate static
  asset before the main application script.

## Validation

Node syntax validation, Ruff, and nine focused unit/integration tests pass. The
regression test explicitly delivers a terminal snapshot followed by the queued
same-revision active snapshot and proves the active snapshot is rejected. The
Console HTTP test proves the installed asset route and main-script binding.

Signed release `fam-os-current-test-20260717-12` is installed and diagnoses
healthy. Its signed manifest SHA-256 is
`c3d0964d3eae8d193ba0e3cbe9d5286354b59bd504a5a3f1d78c9dd4d111ddd3`;
the source and installed browser assets match, and the temporary private release
key was removed.

Two post-install physical tasks exercised both terminal outcomes:

- `c11f7a98-449e-4aec-a545-cb0a129bb872` used an unapproved resource and
  reached a terminal permission-denied result in 0.56 seconds.
- `03ce5ef8-b9a8-408b-a049-621d4731663e` observed the live VS Code editor and
  completed with grounded assurance in 5.23 seconds.

Both tasks have terminal inference and application records in the durable
database. A newly authenticated Console page was opened after the service
restart so the owner can test the installed asset.

## Files changed

- `src/fam_os/console/static/task_updates.js`
- `src/fam_os/console/static/app.js`
- `src/fam_os/console/static/index.html`
- `src/fam_os/console/http.py`
- `tests/unit/test_console_task_updates.py`
- `tests/integration/test_console_http.py`
- `MASTER_PLAN.md`
- `handoffs/README.md`

## Remaining gaps

This removes the identified browser terminal-state race. It does not complete
Phase 23.3 or 23.6: whole-workspace observation/indexing, complete installed
scenario matrices, prolonged concurrent update pressure, soak, rollback,
recovery, and clean removal still require final qualification. Phase 22 real
specialist promotion remains independently open.
