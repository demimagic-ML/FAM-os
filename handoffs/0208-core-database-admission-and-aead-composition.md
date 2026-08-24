# Handoff 0208: Core database admission and AEAD composition

**Date:** 2026-07-19  
**Plan step:** Phase 27.12  
**Status:** Partial  
**Previous handoff:** `0207-sqlite-restart-reconciliation-and-fresh-rollback.md`

## Objective

Prevent model-minted database permits and replace the test-only backup protector
at the product composition boundary.

## Scope completed

- Added Core admission that derives exact `EXECUTE` and `MODIFY` requests from
  trusted plan/candidate state before minting a five-minute permit.
- Rechecks both authorities throughout execution and binds permit expiry in the
  adapter.
- Added plan-owned zero-network/zero-process resource impact and adapter byte/
  progress enforcement.
- Composed retained backups with the installed product's owner-key AES-256-GCM
  cipher and exact associated-data context.
- Proved decision denial has no executor effect, candidate mismatch precedes
  authorization, AEAD context substitution fails, and composition constructs
  the Core service plus recovery adapter.

## Explicitly not completed

- Persistent product grant-ledger, cancellation, audit, Shell, and Console routes.
- Installed artifact and both-profile database scenario evidence.
- Remote database adapters.

## Architecture and decisions

ADR 0180 assigns permit minting to Core and key use to product composition. The
SQLite adapter consumes only inward ports and never receives raw owner key bytes.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/database.py` | Plan-owned resource impact |
| `src/fam_os/core/engineering/database_ports.py` | Permit-expiry control |
| `src/fam_os/core/engineering/database_service.py` | Dual-authority Core admission |
| `src/fam_os/core/engineering/__init__.py` | Service export |
| `src/fam_os/adapters/database/sqlite_engineering.py` | Resource/progress enforcement |
| `src/fam_os/adapters/database/sqlite_fixtures.py` | Strict bounded fixture loader |
| `src/fam_os/product/composition/database_engineering.py` | Owner-key AEAD composition |
| `src/fam_os/product/composition/__init__.py` | Composition exports |
| `tests/unit/test_database_engineering_service.py` | Core admission tests |
| `tests/unit/test_database_engineering_composition.py` | AEAD and factory tests |
| `schemas/v1alpha1/fam.core.database-change-plan.schema.json` | Resource-bound plan schema |
| `docs/decisions/0180-core-mints-database-permits-from-live-dual-authority.md` | Durable admission decision |
| `MASTER_PLANv2.md` | Truthful partial evidence |

## Public interfaces

`DatabaseEngineeringService`, `EngineeringDecisionAuthorizer`,
`CandidateDatabaseExecutor`, `PermitBoundDatabaseControl`,
`ProductDatabaseBackupProtector`, `DatabaseEngineeringUnit`, and
`compose_database_engineering`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --output schemas
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_database_engineering tests.unit.test_database_engineering_service tests.unit.test_database_engineering_composition tests.unit.test_sqlite_database_engineering_adapter tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -p 'test_*.py' -v"
```

Result: 47 focused tests passed, 354 schemas validated, and all 41 architecture
tests passed.

## Evidence and artifacts

- `schemas/v1alpha1/fam.core.database-change-plan.schema.json`
- `docs/decisions/0180-core-mints-database-permits-from-live-dual-authority.md`
- Larry architecture log from the command above

## Known limitations and risks

- Product composition is constructible but not yet reachable through the local
  product's authenticated Shell/Console API.
- The existing engineering grant ledger is in-memory and therefore is not yet a
  restart-safe installed authority source for database work.
- SQLite progress callbacks bound cancellation but a native engine call between
  callbacks may finish before revocation is observed; postconditions still run.

## Operational notes

No installed service, host database, network, or production target was mutated.

## Recommended next entry point

Persist engineering grants and database attempt/audit receipts through Core
storage, then add authenticated proposal/approval/execute/recover/rollback routes
to Shell and Console before installed qualification.
