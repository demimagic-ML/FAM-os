# ADR 0173: Master engineering loop is revisioned and authority-forgetting

Status: Accepted

## Context

Repository inspection, architecture, candidate work, tests, design, dependency
changes, reconciliation, Git, and publication must compose without resetting
budgets or accidentally replaying authority after interruption.

## Decision

The master engineering lifecycle is a strict state machine persisted as a
versioned `EngineeringLoopState`. SQLite WAL updates use optimistic revision
checks. Every transition extends a hash chain and consumes one monotonic token,
wall-time, command, network, file, and storage budget. Dependency and design
evidence attach to the same task record.

Observation and verification stages may resume after restart. Pending workspace
mutation and publication IDs are deliberately cleared on restart; the state
remains at its approval boundary until a new exact checkpoint is recorded.
Multiple coherent changesets are legal, but each has its own checkpoint while
sharing the original budget. Console consumes a read-only projection rather
than owning engineering policy.

## Consequences

- A stale writer cannot overwrite newer task state.
- Restart cannot manufacture or widen confirmation.
- Budget exhaustion fails construction of the next state and cannot reset.
- Receipts remain inspectable across repair, rollback, commit, and publication.

## Evidence

- `src/fam_os/core/engineering/master_loop.py`
- `src/fam_os/adapters/sqlite/engineering_loop.py`
- `src/fam_os/console/engineering.py`
- `tests/unit/test_master_engineering_loop.py`

## Superseded decisions

None.
