# Handoff 0197: Controlled Git and remote publication

**Date:** 2026-07-18  
**Plan step:** Phase 29  
**Status:** Complete  
**Previous handoff:** `0196-verified-design-and-creative-assets.md`

## Objective

Separate reversible local Git delivery from external, credential-bearing,
single-use publication.

## Scope completed

- Added read-only status/history/blame/branch/remote/diff observations.
- Added exact-path branch, stage, commit, and restore actions with hooks disabled.
- Added final publication approval and provider receipt contracts.
- Added opaque-credential Unix publication broker and durable consumption.
- Proved exact test-remote push, draft PR creation, denial, and restart replay.

## Explicitly not completed

- Live third-party provider qualification; the provider-neutral broker boundary
  and local test provider are qualified without external side effects.

## Architecture and decisions

ADR 0172 requires a separate final approval for each remote publication and
distinct authority for exceptional ref operations.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/git_delivery.py` | Git contracts |
| `src/fam_os/core/engineering/git_service.py` | Publication gate |
| `src/fam_os/adapters/git/local.py` | Shell-free local Git |
| `src/fam_os/adapters/git/unix_publication.py` | Opaque provider broker |
| `src/fam_os/adapters/sqlite/publication_consumption.py` | Restart-safe one-use ledger |
| `tests/integration/test_git_publication_exit.py` | Test remote and draft PR exit |

## Public interfaces

`GitRepositoryObservation`, `GitLocalAction`, `GitPublicationApproval`,
`GitPublicationReceipt`, `GitPublicationService`, `LocalGitAdapter`, and
`UnixGitPublicationBroker`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_git_delivery tests.integration.test_git_publication_exit -v
```

Result: five Git tests pass. The exact approved object reaches the bare remote,
the draft record is created, and replay after store reopen is denied.

## Evidence and artifacts

- `docs/decisions/0172-git-publication-requires-a-final-consumed-approval.md`
- Installed suite evidence in `artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt2.json`

## Known limitations and risks

- Live GitHub/GitLab/etc. connectors require separately configured external
  broker implementations and owner-held credentials.

## Operational notes

No remote credential value crosses the Core broker document.

## Recommended next entry point

Read ADR 0173 and Handoff 0198, then inspect master-loop persistence.
