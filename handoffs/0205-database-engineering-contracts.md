# Handoff 0205: Database engineering contracts

**Date:** 2026-07-19  
**Plan step:** Phase 27.12  
**Status:** Partial  
**Previous handoff:** `0204-stable-thread-sanitizer-pairs.md`

## Objective

Define database lifecycle and authority contracts before exposing schema,
migration, fixture, backup, restore, transaction, or rollback effects.

## Scope completed

- Added exact SQLite/PostgreSQL/MySQL targets with candidate through production
  environments and external connection-secret references.
- Added contiguous digest-bound forward and rollback migration steps.
- Restricted fixtures to synthetic, secret-free manifests.
- Added changeset, baseline, authority, backup, rollback, and postcondition
  requirements plus consistent encrypted backup and verification receipts.
- Rejected production mutation without its distinct authority, destructive work
  without backup, and verified/rolled-back states without required evidence.
- Registered and rendered four strict schema roots.

## Explicitly not completed

- SQLite schema/digest, migration, fixture, backup, restore, transaction-test,
  and compensation adapters.
- Remote database adapters, production composition, and installed evidence.

## Architecture and decisions

ADR 0177 makes database mutation a plan-backup-apply-verify-restore lifecycle.
Secrets and engine tools remain outside Core behind adapters.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/database.py` | Database contracts and invariants |
| `src/fam_os/core/engineering/__init__.py` | Public exports |
| `src/fam_os/schemas/catalog.py` | Four schema registrations |
| `tests/contract/schema_database_engineering_fixtures.py` | Representative values |
| `tests/contract/test_schema_roundtrip.py` | Root coverage |
| `tests/contract/test_schema_compatibility.py` | Strict rejection |
| `tests/unit/test_database_engineering.py` | Authority and evidence tests |
| `schemas/v1alpha1/fam.core.database-target.schema.json` | Target schema |
| `schemas/v1alpha1/fam.core.database-change-plan.schema.json` | Plan schema |
| `schemas/v1alpha1/fam.core.database-backup-receipt.schema.json` | Backup schema |
| `schemas/v1alpha1/fam.core.database-verification-receipt.schema.json` | Result schema |
| `docs/decisions/0177-database-engineering-is-plan-backup-apply-verify-restore.md` | Durable lifecycle decision |
| `MASTER_PLANv2.md` | Partial evidence |

## Public interfaces

`DatabaseEngine`, `DatabaseEnvironment`, `DatabaseChangeStatus`,
`DatabaseConsistencyMode`, `DatabaseTarget`, `DatabaseMigrationStep`,
`DatabaseFixtureSet`, `DatabaseChangePlan`, `DatabaseBackupReceipt`, and
`DatabaseVerificationReceipt`, plus four `fam.core` schema roots.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_database_engineering tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src/fam_os/core/engineering/database.py tests/unit/test_database_engineering.py tests/contract/schema_database_engineering_fixtures.py
git diff --check
```

Result: 27 tests passed, 353 schemas validated, compileall and diff checks
passed. The implementation file is 220 lines.

## Evidence and artifacts

- `schemas/v1alpha1/fam.core.database-change-plan.schema.json`
- `docs/decisions/0177-database-engineering-is-plan-backup-apply-verify-restore.md`
- `MASTER_PLANv2.md`

## Known limitations and risks

- Encryption is required by contract, but no encryption adapter exists yet; a
  plain SQLite copy cannot satisfy retained-backup evidence.
- Generic data digests need engine-specific canonicalization rules.
- Remote transactional DDL behavior differs by engine and must be qualified.

## Operational notes

No database, secret, network, or production effect was performed.

## Recommended next entry point

Implement the candidate-only SQLite adapter: canonical schema/data digests,
online snapshot, encrypted artifact port, forward/rollback execution, fixture
loading, restore testing, failure compensation, and exact tests.
