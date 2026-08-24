# ADR 0169: Candidate workspaces reconcile through owned journals

Status: Accepted

## Context

Broad engineering authority requires creating, patching, moving, deleting, and
changing complete project trees. Applying model-proposed operations directly to
an owner's checkout would mix proposal, execution, verification, and authority,
make partial failure destructive, and risk overwriting edits made while FAM_OS
was working. Linux filesystems provide atomic replacement of one directory
entry, but not an atomic commit spanning arbitrary paths in an existing tree.

Self-modification adds a separate hazard: permission to edit a source checkout
must not become permission to alter the running signed installation, active
release selector, trust roots, or live policy.

## Decision

Core owns versioned candidate artifact, operation, baseline, preview, receipt,
and self-update protection contracts. Filesystem behavior remains behind
`CandidateWorkspaceAdapter`.

The adapter captures a sorted, digest-bound baseline and clones it into
owner-private transaction storage outside the owner workspace. It requests a
filesystem copy-on-write reflink and uses an isolated full-copy fallback when
the filesystem does not support reflinks. Every traversed tree and operation
rejects symbolic links. Candidate artifacts are size- and digest-bound and
retain content kind, MIME type, bounded metadata, provenance, and source name.

All mutations and shell-free verification happen in the candidate. The owner
receives one preview binding the baseline, typed operations, bounded text diffs
or binary summaries, risk codes, verification evidence identities, and the
rollback rule. Reconciliation requires a matching explicit approval and
rechecks every affected owner path before the first write.

Reconciliation uses a durable owner-private journal, backup set, atomic
per-path replacements, and an all-or-scoped-rollback protocol. A regular
filesystem cannot make the entire multi-path transition instantaneously
visible, so FAM_OS does not claim whole-tree atomic visibility. On failure it
restores only paths it applied and only while their current state still equals
the recorded FAM_OS post-state. A newer owner edit is preserved and produces a
`recovery_required` receipt. The same journal can restore a completed changeset.

`EngineeringSelfUpdatePolicy` permits paths only inside declared source
checkouts and denies the running installation, trust roots, active release, and
live policy. Promotion remains a separate existing signed build, release,
health-check, activation, and rollback lifecycle.

## Consequences

- Models, tools, and candidate tests cannot mutate the owner workspace before
  approval.
- Stale baselines and symlinked trees fail before reconciliation.
- Interrupted multi-path application is recoverable without treating owner
  state as FAM_OS-owned state.
- Filesystems without reflink support consume full candidate-copy storage.
- Readers can observe an in-progress multi-path reconciliation; the durable
  journal and rollback policy provide transactional recovery, not impossible
  cross-path atomic visibility.
- Phase 26 is component-tested and not yet production-reachable from the signed
  installed Core gateway.

## Alternatives considered

- Edit the owner checkout and rely on Git reset: rejected because untracked
  files, owner edits, non-Git workspaces, and binary assets are not safely
  represented by that rollback model.
- Replace the entire owner workspace directory: rejected because open handles,
  mount points, workspace identity, and unrelated concurrent changes make that
  unsafe and operationally surprising.
- Use hard links as the fallback: rejected because any non-replacement write in
  the candidate could mutate the owner's inode.
- Let source-edit authority update the active installation directly: rejected
  because it bypasses signatures, health checks, activation, and rollback.

## Evidence

- `src/fam_os/core/engineering/transactions.py`
- `src/fam_os/adapters/filesystem/candidate_workspace.py`
- `src/fam_os/adapters/filesystem/candidate_verification.py`
- `tests/unit/test_candidate_workspace.py`
- `tests/contract/schema_transaction_fixtures.py`

## Superseded decisions

None. This extends ADRs 0162 and 0165–0168 without weakening their approval,
authority, verification, or adapter boundaries.
