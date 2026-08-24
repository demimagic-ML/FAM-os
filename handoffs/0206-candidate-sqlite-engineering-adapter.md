# Handoff 0206: Candidate SQLite engineering adapter

**Date:** 2026-07-19  
**Plan step:** Phase 27.12  
**Status:** Partial  
**Previous handoff:** `0205-database-engineering-contracts.md`

## Objective

Implement the first real, candidate-only database lifecycle without granting
network, credential, host, or production authority.

## Scope completed

- Distinguished secret-free candidate SQLite targets from secret-referenced
  PostgreSQL/MySQL targets and added an expiring changeset/host-bound permit.
- Added canonical typed schema and data digests.
- Added engine-native online snapshots protected through an encryption port and
  verified restoration into a disposable database.
- Added one-transaction forward migrations, parameterized synthetic fixtures,
  foreign-key checks, transaction rollback probing, and exact postconditions.
- Rehearsed digest-bound rollback SQL in reverse against a disposable copy and
  compensated the live candidate from backup on verification failure.
- Added live cancellation/revocation checks and replay-resistant attempt state.
- Denied SQLite attachment, detachment, pragmas, virtual tables, and dangerous
  file/extension functions while untrusted SQL executes.
- Added link, stale baseline, tamper, replay, cancellation, revocation, approval,
  rollback, host-escape, backup, restore, and successful fixture tests.

## Explicitly not completed

- Restart reconciliation for an attempt interrupted by process or host failure.
- Core/product composition, real secret-store-backed encryption, installed
  qualification, and both hardware profiles.
- Remote PostgreSQL/MySQL and production adapters.

## Architecture and decisions

ADR 0178 supersedes ADR 0177 only for connection-secret semantics and adds the
candidate SQLite confinement policy. Core owns plan and permit contracts;
SQLite, filesystem, and encryption implementation details remain behind ports
and adapters.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/database.py` | Secret-free candidate SQLite target invariant |
| `src/fam_os/core/engineering/database_ports.py` | Protection, control, and permit ports/contracts |
| `src/fam_os/core/engineering/__init__.py` | Public exports |
| `src/fam_os/adapters/database/` | Digest, policy, storage, execution, and verification adapters |
| `src/fam_os/schemas/catalog.py` | Permit root and corrected target description |
| `tests/contract/schema_database_engineering_fixtures.py` | Permit and nullable-secret fixtures |
| `tests/unit/test_database_engineering.py` | Target invariant coverage |
| `tests/unit/test_sqlite_database_engineering_adapter.py` | Real SQLite positive and hostile matrix |
| `schemas/v1alpha1/fam.core.database-execution-permit.schema.json` | Strict permit schema |
| `schemas/v1alpha1/fam.core.database-target.schema.json` | Corrected target schema |
| `docs/decisions/0178-candidate-sqlite-engineering-is-secret-free-and-confined.md` | Durable confinement decision |
| `MASTER_PLANv2.md` | Truthful partial evidence |

## Public interfaces

`DatabaseBackupProtector`, `DatabaseExecutionControl`,
`DatabaseExecutionPermit`, `SQLiteDatabaseEngineeringAdapter`,
`SQLiteEngineeringResult`, `sqlite_schema_digest`, and `sqlite_data_digest`,
plus `fam.core.database-execution-permit`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_database_engineering tests.unit.test_sqlite_database_engineering_adapter tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src/fam_os/core/engineering/database.py src/fam_os/core/engineering/database_ports.py src/fam_os/adapters/database tests/unit/test_database_engineering.py tests/unit/test_sqlite_database_engineering_adapter.py
git diff --check
```

Result: 38 focused tests passed before the final broad gate; 354 strict schemas
were rendered. Every implementation module remains at or below 298 lines.

## Evidence and artifacts

- `schemas/v1alpha1/fam.core.database-execution-permit.schema.json`
- `docs/decisions/0178-candidate-sqlite-engineering-is-secret-free-and-confined.md`
- `tests/unit/test_sqlite_database_engineering_adapter.py`

## Known limitations and risks

- The attempt file rejects replay but does not yet reconcile a process killed
  between `started` and `verified`.
- Candidate tests use a deterministic fake protector; installed composition must
  prove an authenticated, secret-store-backed protector without checkout imports.
- SQL authorizer containment supplements but does not replace the unprivileged
  product sandbox required for installed execution.

## Operational notes

Tests create only temporary candidate databases. No network, secret, service,
host, or production mutation was performed.

## Recommended next entry point

Add durable restart reconciliation and explicit rollback execution receipts,
then compose the candidate SQLite service through Core/product with a real
protector before beginning remote-engine adapters.
