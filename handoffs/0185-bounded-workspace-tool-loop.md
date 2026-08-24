# Handoff 0185: Bounded workspace tool loop

**Date:** 2026-07-18  
**Plan step:** Phase 19.13 corrective integration  
**Status:** Source and signed installed vertical slice complete  
**Previous handoff:** `0184-owner-workspaces-and-tool-evidence-terminal.md`

## Objective

Turn an explicitly selected owner workspace into a real, bounded implementation
surface: inspect the repository, retrieve relevant files, propose exact edits,
wait for approval, write atomically, re-observe, verify, and undo. Also stop a
new request from being confused with an earlier answer or raw observation data.

## Scope completed

- Separated prior session memory, authorized observations, and the current
  request into distinct inference messages; the current request is always last.
- Added bounded, symlink-safe recursive workspace mapping and relevant UTF-8
  document retrieval.
- Added typed `os.workspace.patch` and `os.workspace.patch.restore`
  capabilities for existing observed files.
- Bound proposed paths and expected SHA-256 values to real retrieval evidence
  inside Core instead of trusting model-supplied authority.
- Required strict JSON mutation output, zero-temperature generation, and a
  context-bounded mutation output budget.
- Derived the executable plan from exact proposed paths rather than displaying
  model-written execution claims.
- Added exact unified-diff preview, explicit owner approval, stale-file
  preconditions, scoped atomic writes, partial-write rollback, re-observation,
  independent postconditions, and exact-byte reversal.
- Made Console forward the selected provider's capability surface so Core can
  reduce it to the least authority required by each request.
- Released only a deterministic, audit-backed action receipt; ordinary model
  prose remains labeled as a model answer with no machine action.
- Built, signed, installed, restarted, and live-probed release
  `fam-os-workspace-loop-20260718-20`.

## Explicitly not completed

- No unrestricted shell, PTY, or model-generated command execution was added.
- This capability does not create or delete files, install packages, or run
  arbitrary commands.
- A patch is limited to four existing retrieved UTF-8 files and 64 KiB total.
- Phase 21.7 still requires a second physical Linux machine.
- Phase 23 external qualification, soak, and human-review gates remain open.

## Architecture and decisions

ADR 0162 defines workspace mutation as an
observe-bind-preview-approve-execute-reobserve-verify transaction. The selected
workspace URI grants the outer scope; retrieval observations grant exact file
authority; the model only proposes content. Core and the deterministic provider
own every authority, transition, hash, write, postcondition, and receipt.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/generation_input.py` | Separate memory, evidence, and current request messages |
| `src/fam_os/core/production/execution_worker.py` | Structured messages and strict mutation generation |
| `src/fam_os/core/production/workspace_parameters.py` | Bind typed model proposals to observed paths and hashes |
| `src/fam_os/core/production/application_worker.py` | Request and bind bounded workspace proposals |
| `src/fam_os/core/production/application_intent.py` | Select map, retrieve, and exact action capabilities |
| `src/fam_os/core/production/application_plan_compiler.py` | Re-observe after mutation before verification |
| `src/fam_os/core/production/action_ingress_router.py` | Require exact authorized action capability |
| `src/fam_os/core/production/application_conditions.py` | Independently hash workspace pre/post state |
| `src/fam_os/core/production/application_reversal.py` | Restore routing and deterministic receipt text |
| `src/fam_os/core/lifecycle/action_receipt_policy.py` | Audit-backed patch and restore receipts |
| `src/fam_os/applications/workspace_capabilities.py` | Canonical workspace capability identifiers |
| `src/fam_os/product/composition/workspace_observations.py` | Bounded map and document retrieval |
| `src/fam_os/product/composition/workspace_patch_contract.py` | Typed patch, preview, result, and reversal records |
| `src/fam_os/product/composition/workspace_patch.py` | Atomic patch and exact-byte restore provider |
| `src/fam_os/product/composition/owner_workspace_capabilities.py` | Workspace capability registration |
| `src/fam_os/product/composition/owner_filesystem.py` | Compose owner workspace observation and action surface |
| `src/fam_os/console/static/app.js` | Preserve selected capabilities for Core least-authority resolution |
| `tests/unit/test_workspace_parameters.py` | Unobserved-path rejection and Core-derived plan proof |
| `tests/unit/test_owner_filesystem.py` | Mapping, symlink, patch, stale-write, and restore proof |
| `tests/integration/test_product_os_workflows.py` | Full approval-bound workspace implementation lifecycle |
| `tests/unit/test_generation_input.py` | Current-request-last and context separation proof |
| `tests/integration/test_product_service.py` | Production message ordering and Console capability regression |

## Public interfaces

- Application capability `os.workspace.map`
- Application capability `os.workspace.retrieve`
- Application capability `os.workspace.patch`
- Application capability `os.workspace.patch.restore`
- Existing Console **Open folder**, **Use folder**, approval, result, and **Undo**
  surfaces now drive the bounded loop.

## Validation

```bash
larry run ".verification-venv/bin/python -m unittest discover -s tests -t ."
.verification-venv/bin/ruff check <changed source and tests>
.verification-venv/bin/mypy <19 changed Python source modules>
node --check src/fam_os/console/static/app.js
jq . artifacts/product/phase19/workspace-tool-loop-20260718.json
```

Result: 1,392 tests passed with two declared skips. Ruff passed for all changed
source and tests, the focused Mypy profile passed 19 source modules, Console
JavaScript syntax passed, and the evidence artifact is valid JSON. The final
full-suite log is
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T18-38-20-858Z.log`.

## Installed proof

The first signed live candidate failed closed before approval with
`application.action.parameters_invalid`; the file remained unchanged. That
probe exposed that mutation generation was not requesting strict JSON. The
corrected runtime now uses JSON output at temperature zero.

The final signed release `fam-os-workspace-loop-20260718-20` is active and
healthy. One Shell session returned `ALPHA` and then `BETA` for two exact
requests without repeating the first answer. A disposable owner workspace then
completed map, retrieve, strict proposal generation, exact preview, approval,
atomic patch, re-observation, and independent verification. The resulting
receipt named the Core-derived plan and exact changed file. Authenticated
Console undo previewed the reverse hashes, required approval, restored the
original bytes, and verified the original SHA-256. Console returned HTTP 200.

## Evidence and artifacts

- `artifacts/product/phase19/workspace-tool-loop-20260718.json`
- `docs/operations/WORKSPACE_TOOL_LOOP.md`
- `docs/decisions/0162-workspace-edits-are-observe-bind-approve-verify-transactions.md`
- Full-suite log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T18-38-20-858Z.log`

## Known limitations and risks

- Recursive mapping is capped at six levels, 128 directories, and 512 files.
- Retrieval is capped at 16 documents, 32 KiB each, and 64 KiB total.
- Generated, dependency, VCS, cache, and symlink trees are excluded.
- The local code expert can still produce an invalid proposal; this now fails
  safely without mutation and should be retried with a narrower request.
- New files, deletion, commands, tests, and package management need separate
  typed providers rather than expansion of patch authority.

## Operational notes

The active signed prefix is `~/.local/share/fam-os-current`, release
`fam-os-workspace-loop-20260718-20`. `fam-os-current.service` is active and the
Console is served at `http://127.0.0.1:8765/`. The disposable probe workspace is
`~/.local/share/fam-os-live-probe-20260718`; its `app.py` was restored to the
original bytes.

## Recommended next entry point

Continue with the next unblocked Master Plan boundary: Phase 23 local release
qualification. Phase 21.7 cannot close until a second physical Linux machine is
available. Add future command, test, create, or delete behavior only as separate
typed, bounded, approval-aware capabilities.
