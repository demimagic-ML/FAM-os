# ADR 0180: Core mints database permits from live dual authority

Status: Accepted

## Context

An adapter accepting a structurally valid permit is not sufficient if untrusted
input can construct that permit. Database work both executes code-like SQL and
modifies persistent candidate state. Its resource impact and target must be
derived from the admitted plan, not model-selected authorization parameters.
Retained backups also need authenticated encryption under installed owner key
material rather than a test cipher.

## Decision

Core is the only composition layer that mints a database execution permit. It
validates task and candidate identity, constructs exact `EXECUTE` and `MODIFY`
authorization requests from the plan, candidate workspace, database path,
changeset, and resource impact, and requires matching live decisions before
calling an adapter. The permit lasts at most five minutes. Execution continues
to re-authorize both requests, and the adapter additionally binds permit expiry.

Candidate database plans declare a zero-network, zero-process, single-tool
resource impact. The SQLite adapter enforces database, retained-backup, and
candidate-input byte bounds and uses a progress handler for live cancellation
and revocation during long engine operations.

Product composition implements backup protection with the existing
owner-master-key `AES-256-GCM` cipher. Associated data binds owner, database
backup type, a digest of the exact plan/target context, and snapshot field.

## Consequences

- Model output cannot mint authority by constructing a permit directly through
  the product service path.
- Candidate SQLite uses no network, subprocess, or secret-injection authority;
  only the product storage key service sees backup key material.
- Production reachability still requires a persisted owner engineering-grant
  service plus Shell/Console routes. A composition factory alone is not installed
  reachability evidence.
- Audit persistence and installed qualification remain mandatory before Phase
  27.12 or Phase 30 can close.

## Evidence

- `src/fam_os/core/engineering/database_service.py`
- `src/fam_os/product/composition/database_engineering.py`
- `tests/unit/test_database_engineering_service.py`
- `tests/unit/test_database_engineering_composition.py`
