# Handoff 0245: Generated documentation apply gate

**Date:** 2026-07-19  
**Plan step:** Phase 30.6, 30.5, and 30.9  
**Status:** Partial  
**Previous handoff:** `0244-trusted-review-passage-gate.md`

## Objective

Attach generated-documentation evidence to active tasks and block stale output
without allowing a model or client to self-issue trusted receipts.

## Scope completed

- Added immutable indexed storage for generation requests, receipts, staleness
  reports, and requirement traces.
- Composed the store with owner-bound AEAD in the installed product root.
- Added an internal trusted-generator admission boundary that re-hashes exact
  candidate source/output files and validates ownership/regeneration files.
- Rejects any symlink component or candidate escape.
- Recomputes and persists staleness before changeset apply and blocks stale,
  missing, or owner-modified generated output.
- Requires satisfied traces to reference real candidate paths and trusted task
  evidence.
- Reconstructs records in natural task progress and exposes authenticated
  Console plus typed Shell read-only queries.

## Explicitly not completed

- Signed generator recipes/adapters for diagrams, API references, runbooks,
  changelogs, or generated code.
- Policy selection that makes particular generated artifacts mandatory.
- Automatic initial generation or regeneration in the natural orchestrator.
- Installed signed-product qualification of this new gate.
- Remaining incident/review adapter stages and other Phase 27/29 gaps.

## Architecture and decisions

ADR 0210 requires Core to derive trust from candidate bytes and persisted task
evidence rather than generator claims. Generated-documentation clients are
read-only; execution remains behind a future signed generator adapter.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/sqlite/engineering_documentation.py` | Immutable indexed documentation records. |
| `src/fam_os/product/engineering_documentation_api.py` | Trusted admission, path hashing, trace validation, and staleness gate. |
| `src/fam_os/product/engineering_loop_api.py` | Enforce current generated output before apply. |
| `src/fam_os/product/composition/engineering_loop.py` | Compose documentation storage. |
| `src/fam_os/product/service.py` | Supply the owner-bound union contract codec. |
| `src/fam_os/product/natural_engineering_api.py` | Reconstruct documentation records. |
| `src/fam_os/console/engineering_loop_routes.py` | Add read-only task documentation route. |
| `src/fam_os/shell/engineering_loop_contracts.py` | Add typed documentation query/response. |
| `src/fam_os/adapters/shell/engineering_loop_dispatch.py` | Dispatch documentation query. |
| `tests/unit/test_product_engineering_documentation_api.py` | Prove re-hashing, staleness, trace evidence, encryption, and symlink denial. |
| `tests/integration/test_console_engineering_loop.py` | Prove Console visibility. |
| `tests/unit/test_fam_shell_engineering_loop_transport.py` | Prove Shell visibility. |

## Public interfaces

- `ProductEngineeringLoopApi.record_generated_documentation(...)` (trusted
  internal adapter boundary)
- `ProductEngineeringLoopApi.record_requirement_trace(...)` (trusted internal
  adapter boundary)
- `ProductEngineeringLoopApi.documentation_for_task(...)`
- `ShellEngineeringLoopOperation.DOCUMENTATION`
- `ShellEngineeringLoopResponse.documentation`
- `GET /api/v1/engineering/tasks/{task_id}/documentation`

## Validation

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_product_engineering_documentation_api \
  tests.unit.test_governed_documentation \
  tests.integration.test_console_engineering_loop \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_product_natural_engineering_api \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_publication \
  tests.integration.test_product_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
git diff --check
```

Result: 406 schemas rendered; 59 tests passed in 6.526 seconds; diff check
passed.

## Evidence and artifacts

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-12-18-282Z.log`
- `docs/decisions/0210-generated-documentation-is-rehashed-before-it-can-gate-apply.md`

## Known limitations and risks

- No generation receipt is produced automatically; the trusted internal entry
  exists for a future signed adapter and is deliberately absent from clients.
- A requirement-selection receipt is still needed to distinguish “not
  required” from “required but missing.”
- Handoff 0243's candidate predates this change and must be rebuilt after the
  governance path is frozen.

## Operational notes

No live service, release, owner project, model, generator, or external system
was changed.

## Recommended next entry point

Define signed generator recipes and a versioned task policy selecting required
artifact kinds. Invoke them inside the candidate sandbox, call the trusted
admission boundary with their real receipts, and add bounded regeneration before
the ordinary changeset checkpoint.
