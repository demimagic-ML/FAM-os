# Handoff 0157: Installed Console and application failure recovery

**Date:** 2026-07-17  
**Plan step:** Phase 23.3, 23.6, and 23.8 readiness  
**Status:** Partial; discovered failures corrected, final qualification remains open  
**Previous handoff:** `0156-phase21-physical-qualification-kit.md`

## Objective

Use the owner-visible installed Shell and Console to test a real VS Code request,
then correct the observed failure lifecycle, task-watching, restart, and signed
update defects without treating the unsuccessful developer workflow as final
application-weaving evidence.

## Scope completed

- Reproduced an out-of-scope VS Code observation that advanced to `Fail safely`
  but never wrote a terminal result.
- Made every application observation or proposal rejection write the failed
  terminal inference result and terminal application state in the same worker
  pass.
- Made Core resume a terminal plan whose inference record is not yet terminal,
  allowing tasks stranded by the previous implementation to reconcile after
  restart.
- Recovered installed tasks
  `task-2c4a06ed-cfa8-4e2d-a39e-be3d2b81b8e1` and
  `task-96be7c17-60a0-41c6-95bd-1b62c71f6364` as durable failed results.
- Replaced overlapping Console SSE/poll behavior with one watcher, one bounded
  poll timer, and revision-aware rendering so an unchanged snapshot does not
  repaint continuously.
- Allowed the loopback-only Console listener to rebind its port immediately
  after clean restart.
- Fixed signed updates so an unchanged persisted `0400` trust key is validated
  and preserved instead of being rewritten and failing with `EACCES`.
- Built, installed, diagnosed, restarted, and ran signed test release
  `fam-os-current-test-20260717-4`.

## Explicitly not completed

- The VS Code connector still exposes only its registered workspace scopes and
  active-editor surfaces; it does not recursively analyze an arbitrary terminal
  working directory.
- Shell contexts remain manually assembled and client-session-local.
- The current registered VS Code scope is
  `file:///home/demimagic/Desktop/NewLLM/`, not the separately requested
  `larry-desktop-app` workspace.
- Phase 21.7 still requires a second physical Linux host.
- Phase 23 installed matrices, 24-hour soak, rollback, removal, and useful
  whole-workspace developer scenario remain open.

## Architecture and decisions

This change enforces the existing invariant that every accepted task reaches a
durable terminal result even when its first external observation is rejected.
It does not change application authority, connector protocol, or public schema.
Console task watching remains SSE-first but closes the stream before bounded
poll fallback and renders only a changed revision, state, or message. No new ADR
was required because these are corrections to existing lifecycle and Console
availability decisions.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/application_worker.py` | Terminalize rejected application observations and proposals |
| `src/fam_os/core/production/gateway.py` | Reconcile a terminal plan with nonterminal inference state |
| `src/fam_os/console/static/app.js` | Single task watcher and revision-aware render fallback |
| `src/fam_os/console/http.py` | Immediate loopback port reuse after restart |
| `src/fam_os/product/bundle_installation.py` | Preserve unchanged read-only trust keys during signed update |
| `tests/integration/test_product_application_fabric.py` | Out-of-scope observation terminalization regression |
| `tests/integration/test_console_http.py` | Console port restart regression |
| `tests/unit/test_signed_bundle_installation.py` | Read-only trust-key update regression |
| `MASTER_PLAN.md` | Current baseline and Phase 23 readiness evidence |

## Public interfaces

No command, schema, storage format, or application connector protocol changed.
Observable corrections are that failed application tasks terminate, unchanged
Console task state no longer blinks, and signed installed updates may reuse an
unchanged persisted trust key.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.integration.test_product_application_fabric \
  tests.integration.test_console_http \
  tests.unit.test_production_task_gateway \
  tests.unit.test_signed_bundle_installation -v
.verification-venv/bin/ruff check \
  src/fam_os/core/production/application_worker.py \
  src/fam_os/core/production/gateway.py \
  src/fam_os/console/http.py \
  src/fam_os/product/bundle_installation.py \
  tests/integration/test_product_application_fabric.py \
  tests/unit/test_signed_bundle_installation.py
node --check src/fam_os/console/static/app.js
larry run env PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
```

Result: focused tests and lint passed. The complete suite passed 1,064 tests
with two declared skips. Signed release `fam-os-current-test-20260717-4`
installed healthy, restarted on Console port 8765, exposed one live VS Code
context, and projected both previously stranded tasks as terminal failures.

## Evidence and artifacts

- Installed prefix: `~/.local/share/fam-os-current`
- Installed release: `fam-os-current-test-20260717-4`
- Full test log:
  `~/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-17T16-53-20-325Z.log`
- No benchmark or physical qualification claim was produced by this correction.

## Known limitations and risks

- A generic model request without application context can still produce an
  unhelpful unverified answer; the product must withhold code-review claims when
  it observed no code.
- Console application choices represent connected instances, not individual
  workspace roots.
- A complete project analysis needs approved recursive indexing and repository
  tools, not only active-editor observation.

## Operational notes

The live test service is `fam-os-current-test.service`, Console is bound to
`127.0.0.1:8765`, and the private runtime root is
`/run/user/1000/fam-os-current`. Restarting the service rotates the Console
bootstrap session; reopen the tokenized Console URL after restart.

## Recommended next entry point

Implement the useful developer-workspace vertical slice before presenting the
application layer as finished: live workspace discovery in Shell and Console,
explicit folder selection, approved recursive project indexing, deterministic
repository tools, grounded code synthesis, and rejection of code-review answers
that contain no observed or indexed project evidence. Begin with
`src/fam_os/console/tasks.py`, `src/fam_os/shell/terminal.py`,
`src/fam_os/product/grounded_retrieval.py`, and the VS Code connector workspace
registration contracts.
