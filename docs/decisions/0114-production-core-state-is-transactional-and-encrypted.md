# ADR 0114: Production Core state is transactional and encrypted

Status: Accepted

## Context

Core's process-local registries lose replay reservations, authority, plan
revision, evidence, and attempt budgets at restart. Reconstructing those values
from model output or retrying mutations would violate authority and replay safety.

## Decision

Production composition uses only the SQLite-backed repository set in
`fam_os.product.composition.core_storage`. Requests, authority, plans, ordered
events, policies, candidate/acceptance/degradation evidence, replay reservations,
and global attempt budgets persist transactionally. Sensitive contracts are
canonical-schema encoded and record-bound encrypted.

Plan creation commits its plan snapshot and first event together. Revision
replacement uses optimistic concurrency and appends exactly the new event in the
same transaction. Global repair/escalation reservations are monotonic and cannot
be rebound to a changed budget after restart.

## Consequences

- Restart no longer clears replay protection or attempt consumption.
- Production Core composition cannot fall back to an in-memory registry.
- Schema compatibility becomes part of durable-state compatibility.
- Phase 17.4 can reconcile actions from authoritative persisted states.

## Evidence

- `src/fam_os/product/composition/core_storage.py`
- `tests/unit/test_durable_core_repositories.py`
- `tests/architecture/test_production_core_storage_boundary.py`
