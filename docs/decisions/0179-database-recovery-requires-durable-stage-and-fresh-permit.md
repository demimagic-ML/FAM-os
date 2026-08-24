# ADR 0179: Database recovery requires durable stage and fresh permit

Status: Accepted

## Context

Replay rejection alone is insufficient after a process or host stops during a
database change. The database may be unchanged, transactionally rolled back, or
committed but not verified. Blind replay can duplicate data or apply a migration
twice. Automatic restore without renewed authority can mutate a database after
the owner's grant has expired or been revoked.

## Decision

The candidate SQLite adapter durably records `started`, then the exact backup
identity, ciphertext digest, size, and candidate-relative path before forward
mutation. Terminal verification records its receipt identity. An interrupted
attempt cannot be replayed.

Reconciliation requires a currently active permit bound to the same approved
changeset and host plus live cancellation/revocation checks. If the database is
already at the exact baseline, reconciliation records a rolled-back result
without restoring. If it differs, only the digest- and size-bound encrypted
backup recorded before mutation may restore it. Missing or malformed recovery
state fails as recovery-required; the adapter does not guess.

An owner-requested rollback of a verified change also requires a fresh permit
whose identity differs from the permit in the verified receipt. It binds the
plan, target, prior receipt, backup receipt, ciphertext, and terminal attempt
state before restoring the exact baseline.

## Consequences

- Every database verification receipt identifies its execution permit.
- Restart recovery and explicit rollback are auditable mutation attempts, not
  ambient startup behavior.
- The current file journal is candidate-local. Product composition must ensure
  its durability and audit integration before installed qualification.
- Remote database adapters need equivalent engine-native durable stages rather
  than reusing SQLite files or assumptions.

## Evidence

- `src/fam_os/adapters/database/sqlite_attempts.py`
- `src/fam_os/adapters/database/sqlite_recovery.py`
- `src/fam_os/core/engineering/database.py`
- `tests/unit/test_sqlite_database_engineering_adapter.py`
