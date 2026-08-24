# ADR 0178: Candidate SQLite engineering is secret-free and confined

Status: Accepted

Supersedes: ADR 0177 where it states that every database target carries a
connection-secret reference. The remainder of ADR 0177 remains accepted.

## Context

ADR 0177 established the plan, backup, apply, verify, and restore lifecycle but
modeled a connection secret on every target. A candidate SQLite database is a
workspace-relative file and needs no credential. Giving it a nominal secret
would overstate authority and could accidentally expose a secret to a local
workflow. Conversely, untrusted SQLite migration SQL can use `ATTACH`, virtual
tables, pragmas, or extension functions to reach beyond the opened database if
the engine is not confined.

## Decision

Candidate SQLite targets carry a candidate-relative database path, no
connection secret, and cannot be relabeled integration, staging, or production.
PostgreSQL and MySQL targets require an opaque connection-secret reference.

Execution requires an expiring permit bound to the exact approved changeset and
host plus live cancellation and revocation checks. Candidate inputs are regular,
single-link files bound by digest. SQLite authorizer policy denies attachment,
detachment, pragmas, virtual tables, and file/extension functions while
untrusted forward or rollback SQL runs.

The adapter takes an engine-native online snapshot, protects it through an
inward encryption port, applies all forward steps and synthetic fixtures in one
transaction, checks exact schema/data and foreign-key postconditions, rehearses
declared rollback SQL against a disposable copy, restores the encrypted backup
into a disposable database, and compensates the live candidate from that backup
after any post-commit verification failure. A private attempt record rejects
replay.

## Consequences

- Candidate SQLite consumes neither network nor secret authority.
- Remote engines need separate adapters and installed qualification; this ADR
  does not authorize them.
- The encryption implementation and key remain outside the database adapter.
- SQLite SQL requiring denied engine features needs a separately designed,
  explicitly authorized recipe rather than a policy exception in candidate mode.
- Restart reconciliation of an interrupted attempt and production composition
  remain required before Phase 27.12 can close.

## Evidence

- `src/fam_os/core/engineering/database.py`
- `src/fam_os/core/engineering/database_ports.py`
- `src/fam_os/adapters/database/`
- `tests/unit/test_sqlite_database_engineering_adapter.py`
- `schemas/v1alpha1/fam.core.database-execution-permit.schema.json`
