# Handoff 0184: Owner workspaces and Tool evidence terminal

**Date:** 2026-07-18  
**Plan step:** Phase 19.12 corrective integration  
**Status:** Source and signed installed vertical slice complete  
**Previous handoff:** `0183-canonical-expert-archives-and-exact-verifiers.md`

## Objective

Make FAM Console grant an explicit local workspace and show real tool execution
instead of allowing model prose to imitate terminal work.

## Scope completed

- Added authenticated owner-home folder navigation and exact file/folder
  selection.
- Added bounded directory listing and file-read Application Fabric
  capabilities.
- Resolved relative create-folder intent beneath the selected workspace while
  preserving approval and verified reversal.
- Added a left workbench with workspace entries and a receipt-backed Tool
  terminal.
- Added a Core activity projection containing observations, proposals, action
  results, resources, timestamps, and receipt IDs.
- Returned exact folder-list results directly from observation evidence without
  model inference.
- Built, signed, installed, restarted, and exercised release
  `fam-os-workspace-20260718-02` against the real FAM_OS folder.

## Explicitly not completed

- There is no arbitrary PTY or raw shell authority.
- Autonomous recursive repository analysis and a bounded multi-step tool loop
  remain Phase 19.13 work.
- The external physical-host, soak, and human-review gates remain open.

## Architecture and decisions

ADR 0161 defines selected workspace URIs as authority and the terminal as an
evidence ledger. Model text never becomes execution input. Exact list questions
are deterministic; synthesis remains available for analysis requests.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/console/workspaces.py` | Owner-scoped folder browser API |
| `src/fam_os/console/task_activity.py` | Application evidence projection |
| `src/fam_os/console/static/workspace.js` | Workspace and tool-ledger behavior |
| `src/fam_os/console/static/workspace.css` | Three-column editorial workbench |
| `src/fam_os/product/composition/owner_filesystem.py` | List/read/action provider |
| `src/fam_os/core/production/deterministic_observation.py` | Exact list result policy |
| `src/fam_os/core/production/action_ingress_router.py` | Selected-workspace action resolution |
| `tests/integration/test_product_os_workflows.py` | Real observation and no-inference proof |
| `tests/integration/test_console_http.py` | Authenticated browser/activity routes |

## Public interfaces

- `GET /api/v1/workspace?path=...`
- `GET /api/v1/tasks/{task_id}/activity`
- Application capabilities `os.directory.list` and `os.file.read`
- Console **Open folder** and **Tool terminal** workbench surfaces

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests -t .
.verification-venv/bin/ruff check <changed source and tests>
.verification-venv/bin/mypy <12 changed Python source files>
node --check src/fam_os/console/static/workspace.js
node --check src/fam_os/console/static/app.js
```

Result: 1,383 tests passed with two declared skips; Ruff, configured Mypy, and
both JavaScript syntax checks passed. A broader ad-hoc `mypy --strict` command
is not a repository qualification profile and reported 202 annotations/type
debts across 11 historically untyped composition modules; no strict-clean claim
is made.

The signed installed probe returned HTTP 200, exact release diagnosis, a
grounded model-free list, `os.directory.inspect` and `os.directory.list`
receipts, and the exact previously-miswritten filename.

## Evidence and artifacts

- `artifacts/product/phase19/workspace-tools-20260718.json`
- `docs/operations/WORKSPACE_TOOL_TERMINAL.md`
- `docs/decisions/0161-workspaces-grant-resource-authority-and-terminals-show-evidence.md`
- Full-suite log: `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T17-40-22-898Z.log`

## Known limitations and risks

- Folder evidence is top-level and bounded to 256 entries.
- File observations are capped at 256 KiB.
- Project-wide analysis still needs controlled recursive discovery, retrieval,
  and multi-step tool choice rather than a larger prompt.
- The current running service is a user transient unit; persistent enablement
  across logout/reboot is separate lifecycle configuration.

## Operational notes

The active signed prefix is `~/.local/share/fam-os-current`, release
`fam-os-workspace-20260718-02`. The live Console is served on loopback port
8765 by `fam-os-current.service` and uses the existing private runtime token.

## Recommended next entry point

Advance Phase 19.13 by defining a bounded Core-owned observe/choose/execute/
reobserve loop using the workspace and receipt contracts from ADR 0161. Do not
add a raw shell to the browser.

