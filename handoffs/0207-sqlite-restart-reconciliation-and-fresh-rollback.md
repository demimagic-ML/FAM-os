# Handoff 0207: SQLite restart reconciliation and fresh rollback

**Date:** 2026-07-19  
**Plan step:** Phase 27.12  
**Status:** Partial  
**Previous handoff:** `0206-candidate-sqlite-engineering-adapter.md`

## Objective

Close candidate SQLite restart ambiguity and prove that explicit rollback cannot
reuse prior mutation authority or a substituted backup.

## Scope completed

- Added fsynced replay state before work and a digest/size/path-bound backup
  stage before forward mutation.
- Added fresh-authority restart reconciliation for unchanged-baseline and
  committed-unverified states.
- Added explicit rollback of a verified change through the exact retained
  encrypted backup.
- Bound every database verification receipt to its execution permit and rejected
  reuse of that permit for explicit rollback.
- Rejected truncated, extended, or digest-substituted retained backups before
  decryption or restore.
- Passed the focused database/schema suite and the complete architecture suite.

## Explicitly not completed

- Core authority-ledger composition and persistent cancellation/audit wiring.
- Authenticated protector composition, installed artifact execution, both
  hardware profiles, or remote database engines.

## Architecture and decisions

ADR 0179 makes recovery a fresh-authority action driven by durable state. It
never silently replays the migration and never infers permission from the
existence of a backup.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/database.py` | Permit identity in receipts |
| `src/fam_os/adapters/database/sqlite_attempts.py` | Durable stage and terminal state |
| `src/fam_os/adapters/database/sqlite_storage.py` | Ciphertext digest/size enforcement |
| `src/fam_os/adapters/database/sqlite_engineering.py` | Record backup stage before mutation |
| `src/fam_os/adapters/database/sqlite_recovery.py` | Restart and explicit rollback adapters |
| `src/fam_os/adapters/database/__init__.py` | Recovery export |
| `tests/unit/test_sqlite_database_engineering_adapter.py` | Restart, rollback, permit, and tamper tests |
| `schemas/v1alpha1/fam.core.database-verification-receipt.schema.json` | Permit-bound result schema |
| `docs/decisions/0179-database-recovery-requires-durable-stage-and-fresh-permit.md` | Recovery decision |
| `MASTER_PLANv2.md` | Partial evidence |

## Public interfaces

`DatabaseVerificationReceipt.execution_permit_id` and
`SQLiteDatabaseRecoveryAdapter.reconcile`/`rollback_verified`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --output schemas
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_database_engineering tests.unit.test_sqlite_database_engineering_adapter tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -p 'test_*.py' -v"
```

Result: 42 focused tests passed, 354 strict schemas validated, and all 41
architecture tests passed. The largest new implementation module is 290 lines.

## Evidence and artifacts

- `schemas/v1alpha1/fam.core.database-verification-receipt.schema.json`
- Larry full architecture log recorded by the command above
- `docs/decisions/0179-database-recovery-requires-durable-stage-and-fresh-permit.md`

## Known limitations and risks

- The product does not yet mint these permits from a live owner grant ledger.
- The source test protector is deterministic and must not be treated as installed
  authenticated-encryption evidence.
- Kill testing currently reconstructs the exact durable stage rather than killing
  an installed process at each stage.

## Operational notes

Only temporary candidate SQLite files were mutated. No service, secret, network,
host, or production action occurred.

## Recommended next entry point

Add the Core database service that mints short-lived permits only from exact live
`EXECUTE` and `MODIFY` decisions, then compose it with `ProductPayloadCipher` and
the installed candidate workspace root.
