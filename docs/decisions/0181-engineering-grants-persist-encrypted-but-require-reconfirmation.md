# ADR 0181: Engineering grants persist encrypted but require reconfirmation

Status: Accepted

## Context

Volatile grants cannot provide owner visibility or an audit trail after restart,
but automatically restoring mutation authority violates the requirement that
restart must not replay expired or previously approved effects.

## Decision

Engineering grants, owner approvals, and authorization decisions are stored in
the private product database with owner-key authenticated encryption. On insert
or replacement, an active grant is not usable until explicitly reconfirmed. On
every secure product-storage start, all previously usable active engineering
grants are atomically marked reconfirmation-required before other product
composition can authorize them.

Authorization decisions are append-only, ordered, encrypted records with a
unique decision identity. Replay fails at the database constraint.

The repository does not authenticate reconfirmation itself. A product authority
service must verify a fresh owner authentication context and, for high-risk
grants, fresh exact break-glass consequences before calling the repository.

## Consequences

- Restart preserves inspectability but restores no mutation authority.
- Database and other engineering services can share one durable grant/audit
  source once the authenticated authority service is composed.
- Shell/Console local transport authentication alone is not yet evidence of
  explicit break-glass confirmation; that route remains open.

## Evidence

- `src/fam_os/product/storage/migrations/0029_engineering_grants.sql`
- `src/fam_os/product/storage/engineering_grant_repository.py`
- `src/fam_os/product/composition/storage_unit.py`
- `tests/unit/test_engineering_grant_repository.py`
