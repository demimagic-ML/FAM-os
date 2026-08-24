# Handoff 0128: Private SQLite WAL storage

**Date:** 2026-07-17  
**Plan step:** Phase 17.1  
**Status:** Complete  
**Previous handoff:** `0127-final-integration-rebaseline.md`

## Objective

Create the durable transactional substrate before replacing any volatile Core
repository.

## Scope completed

- Owner/mode/type/link verified SQLite database creation.
- WAL, full synchronous durability, foreign keys, busy timeout, integrity check.
- Contiguous, bundled, digest-pinned, atomic SQL migrations.
- Initial tables for every final-integration state family.
- Locked transaction API with commit/rollback behavior.
- Packaging declaration for SQL migration resources.

## Explicitly not completed

- Sensitive payload encryption and key recovery are Phase 17.2.
- Domain repository implementations and production swap are Phase 17.3.
- The installed service does not open the database yet.

## Architecture and decisions

ADR 0112 selects one local SQLite WAL database so request-to-action transitions
can be atomic without an external service. Domain boundaries remain enforced by
repositories; raw SQL is not a public Core API.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/storage/database.py` | Private database and migrator |
| `src/fam_os/product/storage/migrations/0001_initial.sql` | Initial durable schema |
| `tests/unit/test_production_database.py` | Security, migration, and transaction tests |
| `docs/decisions/0112-product-state-uses-private-migrated-sqlite-wal.md` | Storage decision |
| `docs/protocols/DURABLE_PRODUCT_STORAGE.md` | Operational protocol |
| `pyproject.toml` | Bundle migration SQL |

## Public interfaces

- `StorageSettings`
- `ProductionDatabase.open()`, `execute()`, `transaction()`, `close()`
- Ordered `fam_os.product.storage.migrations` resources

## Validation

```bash
PYTHONPATH=src:. python3.12 -m unittest tests.unit.test_production_database
.verification-venv/bin/ruff check src/fam_os/product/storage tests/unit/test_production_database.py
PYTHONPATH=src:. .verification-venv/bin/mypy src/fam_os/product/storage
```

Result: six tests passed; lint and typing passed.

## Evidence and artifacts

- `src/fam_os/product/storage/migrations/0001_initial.sql`
- `tests/unit/test_production_database.py`
- ADR 0112

## Known limitations and risks

- SQLite sidecar files inherit protection from the `0700` parent and SQLite's
  database mode; release qualification must recheck them on target filesystems.
- No sensitive production payload may be written before Phase 17.2 completes.

## Operational notes

The database is not opened by the current installed daemon, so this change does
not migrate or modify existing user state.

## Recommended next entry point

Implement Phase 17.2 in `fam_os.product.storage.keys` and `cipher`: create or
load an owner key only for a new database, authenticate record identity as AEAD
associated data, and enter explicit recovery mode when an existing database has
a missing or corrupt key.
