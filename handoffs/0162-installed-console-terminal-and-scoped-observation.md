# Handoff 0162: Installed Console terminal recovery and scoped observation

**Date:** 2026-07-17  
**Plan step:** Phase 23.3, 23.6, and 23.8 readiness  
**Status:** Partial; corrected flow is installed and physically exercised, final Phase 23 gates remain open  
**Previous handoff:** `0161-held-out-evaluation-and-signed-denial.md`

## Objective

Correct the owner-reported Console task that displayed `Fail safely` as active
indefinitely, then prove that a read-only VS Code request without a manually
typed file URI terminates through the signed installed product.

## Root causes

The original task reached a terminal plan but the old Console stopped polling
after a transient status error. Its durable result was reconciled only after a
later service restart. A restart also invalidates the in-memory Console session,
which previously produced another unbounded retry loop. After terminal recovery,
the live request exposed three further integration defects:

- Core rejected an active-editor observation before the connector could resolve
  its resource inside a registered workspace.
- the Console attached every registered action capability to read-only prompts;
- release assembly packaged stale compiled connector JavaScript, and a
  same-version connector update retained the old extension directory.

## Implementation

- Console task polling now retries transient failures with bounded backoff,
  renders only changed snapshots, and stops with an explicit session-expired
  message on HTTP 401.
- Active-editor observations may resolve an unspecified resource only when the
  returned URI is inside the capability's registered scope. Out-of-scope
  provider evidence is rejected by Core.
- The VS Code connector independently refuses active documents outside its
  registered workspace folders before producing an observation payload.
- Console context discovery now separates observation and action capability
  IDs. The current browser task form sends observation capabilities only.
- Complete signed release assembly compiles the VS Code connector before VSIX
  construction.
- Same-version connector updates atomically replace the managed extension,
  validate the staged tree, preserve unmanaged targets, and retain the prior
  target on staging failure.

## Installed evidence

Signed release `fam-os-current-test-20260717-10` is active at
`~/.local/share/fam-os-current`. Installation diagnosis is healthy and the
transient owner service `fam-os-current-test.service` is active on Console port
8765.

The exact browser observation set was exercised against the connected VS Code
instance without a file URI. Request
`c837f5cf-6eee-4677-8807-71095afe725e` produced:

- three succeeded observation steps: diagnostics, active editor, and selection;
- one succeeded local inference step using `qwen2.5-coder:7b`;
- a succeeded release terminal;
- `completed` status with `grounded` assurance and retained content.

The earlier single-observation request
`bea2d87f-0431-4d1f-b35a-45e99c815dca` also completed with grounded assurance.
The final bundle manifest SHA-256 is
`270cd3089483e1650634ff069ba711b043f36874c27f699c81b14f0d9f335d0f`.
The installed VSIX SHA-256 is
`c087923a1a0c079efd4cff241aeb6b5c070758566aabc747c67cd6eb0110acaa`.
The temporary private release key was removed after installation.

## Validation

Focused validation passed 31 tests covering Console HTTP/SSE, application
connector failure and timeout terminalization, scoped active-editor resolution,
out-of-scope evidence rejection, same-version connector update, and deterministic
complete release assembly. Node syntax validation, TypeScript strict checking,
and Ruff passed for the affected files.

## Files changed

- `src/fam_os/console/static/app.js`
- `src/fam_os/console/tasks.py`
- `src/fam_os/core/lifecycle/application_authorization.py`
- `src/fam_os/core/lifecycle/application_service.py`
- `connectors/vscode/src/editor/provider.ts`
- `connectors/vscode/src/editor/observations.ts`
- `src/fam_os/product/release_assembly.py`
- `src/fam_os/product/vscode_installation.py`
- focused unit and integration tests for these boundaries

## Remaining gaps

This proves active-editor weaving, not whole-project understanding. The Console
still needs explicit workspace selection plus approved recursive indexing and
deterministic repository tools before `What's in this project?` can mean the
entire project rather than the currently observed editor state. Phase 23 clean
matrices, 24-hour soak, rollback, recovery, removal, and Phase 21.7 two-physical-
host evidence remain open. Reload the VS Code window once so the running
extension host uses the newly installed connector-side workspace guard.

