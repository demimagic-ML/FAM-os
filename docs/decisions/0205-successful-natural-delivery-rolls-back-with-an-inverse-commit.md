# ADR 0205: Successful natural delivery rolls back with an inverse commit

Status: Accepted

## Context

The installed natural engineering slice applied a journaled changeset,
reverified it, and immediately created an evidence-bound local commit. The
existing rollback transition covered only an interrupted apply before commit.
Restoring the filesystem after a successful commit without recording a second
Git effect would leave a dirty worktree, hide history, and make restart
reconciliation ambiguous.

## Decision

A post-success rollback is a separate exact owner checkpoint. Its digest binds
the task, candidate, applied changeset preview, apply journal, applied paths,
and current FAM-created Git head. Core persists rollback intent before restoring
anything and reauthorizes every affected path immediately before the effect.

The candidate journal restores only paths whose current state still equals the
recorded FAM-applied state. Concurrent owner changes are preserved and make the
rollback recovery-required. A complete restore is staged only for the original
changeset paths and committed as a new local commit. History is never reset,
amended, or force-written. Candidate rollback and inverse-commit receipts are
both required before the master lifecycle reaches `rolled_back`.

The same persisted rollback intent and local delivery records reconcile a
retry after process interruption without creating a second commit. Console and
Shell expose the rollback as an optional third approval after successful local
delivery.

## Consequences

- Successful delivery has an explicit, auditable, history-preserving rollback.
- Unrelated or newer owner work is never overwritten to make rollback appear
  complete.
- Rollback requires the original task grant to remain live; an expired or
  revoked grant fails closed.
- A remote branch that already contains the original commit is not changed by
  this local rollback. Publishing the inverse commit remains a separate exact
  publication action.
- Historical candidate changeset documents are migrated only inside the SQLite
  storage adapter to add the new canonical rollback fields; public decoding
  stays strict.

## Alternatives considered

- Reset or amend the original commit: rejected because it rewrites history and
  makes external reconciliation unsafe.
- Restore files without a Git commit: rejected because it leaves an
  unaccounted dirty worktree.
- Revert from Git alone: rejected because the candidate apply journal is the
  authority that distinguishes FAM-owned state from concurrent owner changes.
- Treat the original changeset approval as rollback approval: rejected because
  rollback is a later mutation with a different current-state boundary.

## Evidence

- `src/fam_os/core/engineering/candidate_changeset.py`
- `src/fam_os/core/engineering/candidate_changeset_service.py`
- `src/fam_os/core/engineering/local_git_delivery.py`
- `src/fam_os/core/engineering/lifecycle_driver.py`
- `src/fam_os/product/natural_engineering_api.py`
- `tests/integration/test_natural_engineering_checkpoint.py`

## Superseded decisions

None.
