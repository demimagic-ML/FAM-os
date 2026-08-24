# ADR 0172: Git publication requires a final consumed approval

Status: Accepted

## Context

Local branch and commit work is reversible within an owner workspace. Pushes,
pull requests, force pushes, protected refs, tags, and remote changes affect
other people and systems and cannot inherit local mutation approval.

## Decision

Read-only Git observation and exact-path local actions use a shell-free adapter
with system/global configuration, prompting, credentials, and hooks disabled.
Commits bind the approved changeset and verification evidence.

Remote publication requires an expiring single-use `GitPublicationApproval`
binding the remote URL digest, source and target refs, expected old and proposed
new object IDs, commits, complete diff digest, verification, title/body,
credential reference, and consequence preview. A provider-neutral Unix broker
receives only the opaque credential reference. Durable SQLite consumption is
recorded before the effect, so crash or restart cannot replay approval.
Force/protected/tag/remote mutation additionally requires its distinct exact
owner authority; it remains denied by default.

## Consequences

- Local engineering never silently becomes external publication.
- Provider credentials remain outside Core, models, prompts, logs, and receipts.
- A remote ref change after approval fails before publication.
- Retry after uncertain publication requires reconciliation and a new approval.

## Evidence

- `src/fam_os/core/engineering/git_delivery.py`
- `src/fam_os/core/engineering/git_service.py`
- `src/fam_os/adapters/git/local.py`
- `src/fam_os/adapters/git/unix_publication.py`
- `tests/integration/test_git_publication_exit.py`

## Superseded decisions

None.
