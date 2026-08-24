# ADR 0177: Database engineering is plan, backup, apply, verify, and restore

Status: Accepted

## Context

Database changes can be syntactically valid while corrupting data, violating
constraints, leaking production credentials, or leaving no usable rollback.
A migration command or copied database file is not sufficient evidence of a
safe database lifecycle.

## Decision

Core admits database work through an exact target containing an external secret
reference, never credentials. A change plan binds the baseline schema and data
digests, ordered forward and rollback artifacts, fixtures, backup requirement,
authorities, approved changeset, and postconditions.

Destructive work requires a consistent encrypted backup and explicit rollback.
Fixtures are synthetic and secret-free. Production targets additionally require
`PRODUCTION_MUTATE`. A verified result requires applied-step identities,
transactional tests, restore testing, final schema/data digests, and exact
postconditions. Partial failure ends as failed, rolled back, or
`recovery_required`; it cannot be labeled verified.

## Consequences

- SQL remains an untrusted candidate artifact referenced by path and digest.
- Engine clients, backup tools, and secret stores stay behind adapters.
- Candidate SQLite can use an unprivileged local adapter; remote and production
  effects require their exact network, secret, and production authorities.
- Installed qualification must prove backup restoration and failed-migration
  compensation, not only successful forward migration.

## Evidence

- `src/fam_os/core/engineering/database.py`
- `tests/unit/test_database_engineering.py`
- `tests/contract/schema_database_engineering_fixtures.py`
