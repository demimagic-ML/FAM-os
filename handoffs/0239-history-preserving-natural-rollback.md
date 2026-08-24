# Handoff 0239: History-preserving natural rollback

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, and 30.9  
**Status:** Partial (`source_composed`)  
**Previous handoff:** `0238-direct-installed-engineering-coverage.md`

## Objective

Make rollback a real owner-controlled continuation of a successful natural
engineering delivery rather than a projection or an interrupted-apply-only
state.

## Scope completed

- Added an exact rollback checkpoint bound to the applied preview, journal,
  paths, and current FAM-created Git head.
- Persisted candidate rollback intent before effect and reauthorized each path
  immediately before restoring it.
- Preserved concurrent owner changes and surfaced incomplete rollback as
  recovery-required.
- Added a replay-safe exact-path inverse local Git delivery that creates a new
  commit and never resets or amends history.
- Required both the candidate rollback receipt and inverse Git receipt before
  the master loop reaches `rolled_back`.
- Added authenticated Console and same-owner Shell rollback controls.
- Added a storage-local migration for pre-rollback candidate changeset
  documents while keeping public schema decoding strict.

## Explicitly not completed

- Signed installed rollback qualification; current evidence is source-composed.
- Remote publication of either the original or rollback commit.
- Phase 30.1/30.5/30.9 in full, governance attachment, remaining specialized
  powers, final matrices, soak, or human review.

## Architecture and decisions

ADR 0205 requires successful rollback to preserve history with a separate
inverse commit and forbids overwriting concurrent owner work.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/candidate_changeset.py` | Explicit rollback state and digest |
| `src/fam_os/core/engineering/candidate_changeset_service.py` | Durable authorized rollback policy |
| `src/fam_os/adapters/filesystem/candidate_workspace.py` | Idempotent rollback-journal reconciliation |
| `src/fam_os/core/engineering/local_git_delivery.py` | Replay-safe inverse local commit |
| `src/fam_os/core/engineering/lifecycle_driver.py` | Compound candidate/Git rollback admission |
| `src/fam_os/core/engineering/master_loop.py` | Committed-to-rolled-back transition |
| `src/fam_os/product/candidate_engineering_api.py` | Product candidate rollback facade |
| `src/fam_os/product/engineering_loop_api.py` | Rollback checkpoint and delivery composition |
| `src/fam_os/product/natural_engineering_api.py` | Exact natural rollback ceremony |
| `src/fam_os/console/natural_engineering_routes.py` | Authenticated rollback route |
| `src/fam_os/console/static/natural_engineering.js` | Optional rollback approval UI |
| `src/fam_os/adapters/shell/natural_engineering.py` | Shell rollback checkpoint and outcome |
| `src/fam_os/adapters/sqlite/engineering_candidate_changeset.py` | Historical wire-shape migration |
| `schemas/v1alpha1/fam.core.candidate-changeset.schema.json` | Rendered strict rollback fields/statuses |

## Public interfaces

- `CandidateChangesetStatus` adds `rollback_intent`,
  `explicitly_rolled_back`, and `rollback_recovery_required`.
- `CandidateChangesetRecord` adds the exact rollback decision, authorization
  IDs, and rollback receipt.
- Console adds `POST /api/v1/engineering/natural-language/proposals/{id}/rollback`.
- Shell exposes `engineering.changeset.rollback` as an optional third approval.

## Validation

```bash
.verification-venv/bin/python tools/render_contract_schemas.py --output schemas
.verification-venv/bin/python -m unittest \
  tests.unit.test_candidate_changeset_service \
  tests.unit.test_candidate_workspace \
  tests.unit.test_local_git_delivery_service \
  tests.unit.test_git_delivery \
  tests.unit.test_engineering_lifecycle_driver \
  tests.unit.test_master_engineering_loop \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_product_natural_engineering_api \
  tests.unit.test_fam_shell_natural_engineering \
  tests.integration.test_console_natural_engineering \
  tests.integration.test_natural_engineering_checkpoint \
  tests.contract.test_schema_compatibility \
  tests.contract.test_static_configuration_schemas \
  tests.architecture.test_product_composition_boundary \
  tests.architecture.test_production_core_storage_boundary \
  tests.security.test_engineering_adversarial -v
```

Result: 63 tests pass; all 400 schemas render and validate. The direct natural
integration applies, commits, rolls back to the exact original content, creates
one separate rollback commit, and reconstructs the terminal rollback outcome.

## Evidence and artifacts

- Larry log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T08-05-18-328Z.log`
- `docs/decisions/0205-successful-natural-delivery-rolls-back-with-an-inverse-commit.md`

## Known limitations and risks

- Rollback has not yet been exercised from a newly built signed installed
  release.
- Publication remains component-only and requires a separate product ceremony
  and configured credential-opaque broker.

## Operational notes

No running user service or installed release was changed. The service on
`127.0.0.1:8765` remains outside this source-only validation.

## Recommended next entry point

Finish the optional publication tail of Phase 30.1. Compose the existing
provider-neutral broker and single-use consumption store into the product,
permit a separate task-scoped publish grant, derive the final approval from
observed Git state, and expose it through the same Console/Shell lifecycle.
