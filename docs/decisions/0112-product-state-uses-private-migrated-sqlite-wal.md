# ADR 0112: Product state uses private migrated SQLite WAL

Status: Accepted

## Context

The installed service needs atomic state across requests, plans, approvals,
actions, evidence, experts, connectors, and adaptation without adding an
external database service to a single-user workstation product.

## Decision

FAM_OS uses one owner-private SQLite database in WAL mode with foreign keys,
full synchronous durability, busy timeout, integrity checks, and ordered
digest-pinned migrations. The containing directory is mode `0700`; the database
is mode `0600`, owned by the effective user, not a symlink, and has one hard
link. Unknown future migrations and changed migration digests fail startup.

Sensitive columns are named and reserved as ciphertext. Phase 17.2 supplies the
owner-bound encryption key lifecycle before any sensitive production payload is
written. Domain repositories, not callers, own SQL access after Phase 17.3.

## Consequences

- Multi-table transitions can commit or roll back atomically.
- Restart reconciliation has one durable source of truth.
- Release bundles must include every SQL migration.
- Missing, corrupt, or incompatible storage blocks normal startup instead of
  silently rebuilding state.

## Alternatives considered

- Separate JSON/JSONL files. Rejected because cross-domain state transitions
  cannot be committed atomically.
- A system database daemon. Rejected for the local owner-scoped baseline.
- One database per subsystem. Deferred because cross-subsystem crash consistency
  is the immediate requirement; repositories still enforce domain ownership.

## Evidence

- `src/fam_os/product/storage/database.py`
- `src/fam_os/product/storage/migrations/0001_initial.sql`
- `tests/unit/test_production_database.py`
