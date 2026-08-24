# Handoff 0244: Trusted review passage gate

**Date:** 2026-07-19  
**Plan step:** Phase 30.8, 30.5, and 30.9  
**Status:** Partial  
**Previous handoff:** `0243-integrated-signed-candidate-host-blocked.md`

## Objective

Attach independent review checkpoints to the active task and make real open
findings block the exact changeset without allowing clients or models to
self-attest review success.

## Scope completed

- Added owner-scoped trusted checkpoint attachment with exact task, candidate,
  and changeset-digest validation.
- Made all attached checkpoints for a changeset passage gates before apply.
- Preserved the existing optimistic, restart-safe finding resolution/waiver
  state machine.
- Composed review persistence into the product loop with owner-bound AEAD,
  indexed task lookup, WAL/FULL durability, and narrow plaintext migration.
- Added natural task progress reconstruction for attached reviews.
- Added authenticated Console and typed Shell read-only review queries.
- Kept checkpoint creation and claimed resolution identifiers out of both
  client transports.

## Explicitly not completed

- A production signed reviewer adapter or independent human-review ingestion
  ceremony.
- Policy selection of required code/security/architecture/design disciplines.
- Typed resolution-receipt lookup and owner-authenticated truthful waiver UI.
- Signed installed and live-product qualification of the review gate.
- Phase 30.6 documentation workflows or the remaining incident stages.

## Architecture and decisions

ADR 0209 makes trusted adapter attachment the only product entry for review
checkpoints. Once attached, a blocked checkpoint is enforced by the ordinary
apply path and cannot be bypassed by Console or Shell.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/review_service.py` | Add inspection, task listing, and owned closure. |
| `src/fam_os/adapters/sqlite/engineering_review.py` | Add encrypted indexed product persistence and migration. |
| `src/fam_os/product/engineering_review_api.py` | Bind trusted checkpoints to exact Core state and enforce passage. |
| `src/fam_os/product/engineering_loop_api.py` | Gate apply and expose review state. |
| `src/fam_os/product/composition/engineering_loop.py` | Compose the review service. |
| `src/fam_os/product/service.py` | Supply the owner-bound review codec. |
| `src/fam_os/product/natural_engineering_api.py` | Reconstruct reviews in task progress. |
| `src/fam_os/console/engineering_loop_routes.py` | Add authenticated read-only review listing. |
| `src/fam_os/shell/engineering_loop_contracts.py` | Add the typed `REVIEWS` query/response operation. |
| `src/fam_os/adapters/shell/engineering_loop_dispatch.py` | Dispatch review queries. |
| `tests/unit/test_product_engineering_review_api.py` | Prove exact binding, blocking, trusted resolution, and candidate denial. |
| `tests/unit/test_engineering_review_service.py` | Prove encrypted migration and indexed task lookup. |
| `tests/integration/test_console_engineering_loop.py` | Prove Console review visibility. |
| `tests/unit/test_fam_shell_engineering_loop_transport.py` | Prove Shell review visibility. |

## Public interfaces

- `ProductEngineeringLoopApi.record_trusted_review(...)` (internal trusted
  product boundary, not a client transport)
- `ProductEngineeringLoopApi.reviews_for_task(...)`
- `ShellEngineeringLoopOperation.REVIEWS`
- `ShellEngineeringLoopResponse.reviews`
- `GET /api/v1/engineering/tasks/{task_id}/reviews`

## Validation

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_review_service \
  tests.unit.test_product_engineering_review_api \
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

Result: 406 schemas rendered; 58 tests passed in 6.579 seconds; diff check
passed.

## Evidence and artifacts

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T09-07-11-284Z.log`
- `docs/decisions/0209-only-trusted-review-adapters-may-create-blocking-checkpoints.md`

## Known limitations and risks

- Absence of a checkpoint is not yet proof that policy selected no review; the
  production selector must create a durable selection receipt.
- Review resolution remains a trusted internal service call. A transport route
  must not be added until it resolves a real typed remediation receipt.
- The candidate from Handoff 0243 predates these review changes and must be
  rebuilt after the governance path is frozen.

## Operational notes

No service, model, active release, owner workspace, or external reviewer was
changed or contacted.

## Recommended next entry point

Add a versioned review-selection policy and signed reviewer adapter that emits
attributable findings over the exact candidate/changeset digest. Then connect
typed remediation receipts and truthful owner waivers before installed
qualification.
