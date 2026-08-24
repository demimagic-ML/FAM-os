# ADR 0208: Protected local refs derive an exact feature branch

Status: Accepted

## Context

The natural publication path correctly refused to publish from `main`,
`master`, `trunk`, `production`, or `prod`, but required the owner to create and
select a feature branch manually before asking FAM_OS to work. That broke the
ordinary natural-language lifecycle and left automatic branching outside its
restart-safe Git intent.

## Decision

When a locally approved, reverified changeset is ready for its local commit and
the repository is on a protected local branch, Core deterministically derives a
task-specific `fam/...` feature branch. The branch action is stored in the same
local-delivery record before mutation and receives a separate live `modify`
authorization decision.

Branch creation must preserve the exact observed head object. If the process
stops after creating the branch but before persisting its receipt, restart may
reconcile only when the current branch name and head exactly match the recorded
intent. An existing derived branch while the protected branch remains checked
out is a collision and stops safely; it is never reused or overwritten.

Repositories already on a non-protected branch keep that branch. Remote
publication remains a later credential-opaque proposal and separate
`publish + secret_use` owner grant under ADR 0206.

## Consequences

- An owner can begin a natural push/PR task on the repository's ordinary main
  branch without manual Git preparation.
- The approved content is committed on a new feature ref, not on the protected
  ref.
- A crash cannot create a second branch or silently accept an unrelated branch
  with the same name.
- No protected-ref-write authority is inferred.
- Phase 30.1 remains open until this source path and the other open lifecycle
  capabilities are built and proved from the signed installed product.

## Alternatives considered

- Commit on the protected branch and create a feature ref afterward. Rejected
  because the protected ref would already have moved.
- Reuse an existing deterministic feature branch. Rejected because its
  ownership and head may differ from the recorded task intent.
- Require the owner to run Git commands first. Rejected because feature-branch
  preparation is part of the requested complete natural lifecycle.

## Evidence

- `src/fam_os/core/engineering/local_git_delivery.py`
- `src/fam_os/adapters/git/local.py`
- `tests/unit/test_local_git_delivery_service.py`
- `tests/integration/test_natural_engineering_publication.py`

## Superseded decisions

None. This extends ADRs 0172, 0202, and 0206.
