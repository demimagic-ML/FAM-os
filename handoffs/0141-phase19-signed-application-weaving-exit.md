# Handoff 0141: Phase 19 signed application-weaving exit

**Date:** 2026-07-17  
**Plan step:** Phase 19.10 and Phase 19 exit  
**Status:** Complete  
**Previous handoff:** `0140-explicit-production-desktop-fallbacks.md`

## Objective

Complete the Console execution spine, direct deterministic undo, SSE edge
behavior, bundled fonts, and the full installed Phase 19 exit against real VS
Code without model-generated authority or source-only acceptance evidence.

## Scope completed

- Added a durable Core-owned reversal service that reuses no model output,
  re-observes the exact resource revision, requires normal approval, and releases
  only a safe verified result.
- Persisted source/reversal linkage with compare-and-swap claiming. Concurrent
  reversal is rejected, cancellation remains retryable, and successful token
  consumption is terminal.
- Added Console reversal status/undo APIs and an Undo control using the same task
  stream, approval, evidence, and result surfaces as every other action.
- Closed SSE invalid/future cursor, missing task, terminal replay, resume, and
  bounded connection-close behavior.
- Preserved immutable connector previews as structured JSON and removed the
  opaque reversal token from the VS Code human-visible undo preview.
- Bundled Noto Sans, Noto Sans Mono, and Noto Serif Display regular/bold or
  medium faces with the SIL OFL 1.1 license; served only allowlisted font assets
  under the Console CSP and included them in the wheel.
- Added a repeatable signed installed exit runner split into small release,
  Console, VS Code process, and scenario modules.
- Corrected a transient confirmation visibility race so a plan cannot surface
  `shell.core_unavailable` while its proposal record is finishing persistence.

## Explicitly not completed

- Phase 18.6 Python, retrieval, mathematics, and media declared verifier binding.
- Phase 20 memory/retrieval/adaptation production composition.
- Phase 21 physical multi-device qualification, Phase 22 real LoRA/QLoRA
  factory, or Phase 23 final matrices, soak, and independent human review.

## Architecture and decisions

ADR 0123 makes reversal a deterministic Core task rather than a model prompt or
connector bypass. The token remains in encrypted private evidence. The source
application record owns one durable active reversal link; the reversal record
links back to its source. Normal permission, confirmation, action, verification,
and final-result policy remain mandatory.

SSE responses are bounded connections that close after terminal replay or the
stream window. EventSource reconnects with `Last-Event-ID`; terminal and ordinary
HTTP clients receive deterministic EOF.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/application_reversal.py` | Deterministic reversal lifecycle and safe result. |
| `src/fam_os/core/production/application_contracts.py` | Durable source/reversal linkage. |
| `src/fam_os/core/production/application_gateway.py` | Structured previews and transient approval handling. |
| `src/fam_os/console/` | Undo API/UI, strict SSE, and packaged font serving. |
| `connectors/vscode/src/editor/workspace-actions.ts` | Token-free human undo preview. |
| `tools/phase19_exit/` | Small installed qualification components. |
| `tools/run_phase19_exit.py` | Reproducible signed exit command. |
| `artifacts/product/phase19/phase19-exit.json` | Raw passing installed evidence. |

## Public interfaces

- `GET /api/v1/tasks/{task_id}/reversal`
- `POST /api/v1/tasks/{task_id}/undo`
- Packaged `/fonts/<allowlisted-name>.ttf` Console assets
- `tools/run_phase19_exit.py`
- Optional application execution fields `reversal_source_session_id` and
  `reversal_session_id`

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests -t .
.verification-venv/bin/ruff check .
.verification-venv/bin/python -m unittest discover -s tests/architecture -t .
npm --prefix connectors/vscode test
FAM_OS_RUN_VSCODE_LIVE=1 .verification-venv/bin/python -m unittest tests.integration.test_vscode_connector_live_acceptance -v
.verification-venv/bin/python tools/run_phase19_exit.py
```

Results: 926 Python tests pass with two declared skips; 39 architecture tests
pass; Ruff passes; affected production and tool modules pass Mypy; seven
TypeScript tests, native transport integration, and ten connector schemas pass;
the opt-in isolated live VS Code test passes. The signed installed report has
`passed: true` for all summary, unittest, preview, edit, undo, privacy,
diagnosis, and removal checks.

## Evidence and artifacts

- `artifacts/product/phase19/phase19-exit.json`
- `docs/decisions/0123-core-owns-deterministic-application-reversal.md`
- `docs/operations/PHASE19_SIGNED_EXIT.md`

## Known limitations and risks

- The test signing key is ephemeral evidence, not a production trust anchor.
- The installed run proves this Linux workstation and VS Code build; Phase 23
  still owns clean-profile matrices and final release qualification.
- Whole-tree strict Mypy still has pre-existing findings outside the affected
  profile; final clean profile qualification remains explicit Phase 23 work.

## Operational notes

The runner uses an isolated temporary install and VS Code profile. It connects
to existing local Ollama without downloading or changing models. It removes the
installation and process groups after the run.

## Recommended next entry point

Return to Phase 18.6 before beginning Phase 20. Read the verifier package/runtime
binding contracts and `ProductionTaskGateway`; make declared Python, retrieval,
mathematics, and media verifiers selected and invoked through the production
path with exact evidence and no acceptance weakening.
