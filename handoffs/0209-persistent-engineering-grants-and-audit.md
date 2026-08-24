# Handoff 0209: Persistent engineering grants and audit

**Date:** 2026-07-19  
**Plan step:** Phase 27.12 production authority dependency  
**Status:** Partial  
**Previous handoff:** `0208-core-database-admission-and-aead-composition.md`

## Objective

Provide restart-safe owner visibility and authorization audit without restoring
database mutation authority after restart.

## Scope completed

- Added migration 0029 for encrypted engineering grants and append-only
  authorization decisions.
- Added repository storage/retrieval, explicit reconfirmation state, restart
  invalidation, usable-state filtering, and ordered decision audit retrieval.
- Wired secure product-storage startup to invalidate all active engineering
  grants before product services can use them.
- Proved encrypted round trips, replay rejection, and restart reconfirmation.
- Re-ran existing secure-storage and product storage-mode integration tests.

## Explicitly not completed

- Fresh owner-authentication and break-glass reconfirmation service.
- Shell/Console grant inspection, activation, revocation, and audit routes.
- Database service wiring to this persistent authorizer.

## Architecture and decisions

ADR 0181 separates durable visibility from live authority. Repository methods
store state; they do not decide whether an owner authentication context is valid.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/storage/migrations/0029_engineering_grants.sql` | Durable grant/audit schema |
| `src/fam_os/product/storage/engineering_grant_repository.py` | Encrypted repository |
| `src/fam_os/product/composition/core_storage.py` | Repository composition |
| `src/fam_os/product/composition/storage_unit.py` | Restart invalidation |
| `tests/unit/test_engineering_grant_repository.py` | Persistence/restart/audit tests |
| `docs/decisions/0181-engineering-grants-persist-encrypted-but-require-reconfirmation.md` | Durable authority decision |

## Public interfaces

`SqliteEngineeringGrantRepository` and
`CoreRepositorySet.engineering_grants`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_engineering_grant_repository tests.unit.test_secure_product_storage tests.integration.test_product_service_storage_modes -v
```

Result: all 9 storage and integration tests passed.

## Evidence and artifacts

- Migration 0029
- ADR 0181
- Repository test suite

## Known limitations and risks

- `mark_reconfirmed` is intentionally a repository primitive and must never be
  exposed directly to clients.
- The authenticated product authority service and break-glass consequence flow
  are still required before any persisted grant becomes production-reachable.

## Operational notes

Tests used temporary owner-private databases. Existing product databases will
apply migration 0029 during the normal ordered startup transaction.

## Recommended next entry point

Implement a Core/product persistent authorizer that validates fresh owner proof,
reactivates the in-memory policy ledger, persists every decision, and exposes
only authenticated Shell/Console operations.
