# Handoff 0264: Generated workspace links are pruned

**Date:** 2026-07-19  
**Plan step:** Phase 30.1 repository inspection and candidate creation  
**Status:** Partial (`source_composed`; developer Console proven)  
**Previous handoff:** `0263-natural-postgresql-migration-lifecycle.md`

## Objective

Allow a normal npm/Next.js repository to enter the natural engineering
lifecycle without following generated dependency/cache links or weakening
source-path protection.

## Scope completed

- Reproduced `403 workspace trees cannot contain symbolic links` against the
  owner-selected `B2B-DIS-Platform` repository.
- Confirmed the links were in `.next` and `node_modules/.bin`.
- Pruned a closed non-authoritative directory set before repository validation,
  observation, and candidate cloning.
- Preserved rejection of source symlinks, hardlinks, candidate links, and link
  traversal on exact operation paths.
- Added a regression containing both dependency and cache links.
- Proved the real repository now produces 138 authoritative observations and a
  238-entry link-free candidate with no dependency/cache entries.
- Restarted `fam-os-natural-dev.service` on port 8877 and reopened an
  authenticated isolated browser window.

## Explicitly not completed

- Generated dependency trees are not copied or trusted.
- This does not prove project-specific npm/Next.js build commands; those may
  require a qualified toolchain or integration environment.
- The owner has not yet loaded `fam-os-userns`, so mutation diagnostics still
  fail closed at the production sandbox boundary.
- No signed release or live port-8765 promotion was performed.

## Architecture and decisions

ADR 0227 defines generated directories as pruned, non-authoritative inputs.
Authoritative source paths retain strict no-link semantics.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/filesystem/candidate_io.py` | Prune closed directories before link validation |
| `src/fam_os/adapters/filesystem/repository_evidence.py` | Bounded non-following observation |
| `src/fam_os/adapters/filesystem/candidate_workspace.py` | Link-free authoritative candidate clone |
| `tests/unit/test_engineering_preparation_orchestrator.py` | Generated-link regression |
| `docs/decisions/0227-generated-dependency-trees-are-pruned-not-followed.md` | Durable policy |

## Public interfaces

No wire contract changed. `reject_tree_symlinks` accepts an optional closed
directory-pruning set for owner-tree callers; candidate trees still use strict
validation.

## Validation

```bash
PYTHONPATH=src .verification-venv/bin/python -m unittest -v \
  tests.unit.test_engineering_preparation_orchestrator \
  tests.unit.test_candidate_workspace \
  tests.unit.test_candidate_generation \
  tests.security.test_engineering_adversarial
```

Result: the focused 23 tests passed in 0.314 seconds; the broader candidate,
repository, natural-execution, and adversarial matrix passed 73 tests in 0.678
seconds; all 41 architecture tests passed. Real repository observation and
candidate creation also passed with 138 files, 238 candidate entries, and zero
excluded dependency entries copied.

## Evidence and artifacts

- ADR 0227
- Larry log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T15-22-37-834Z.log`
- Broader regression log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T15-26-10-150Z.log`
- Architecture log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T15-26-24-007Z.log`

## Known limitations and risks

- A repository that intentionally places authoritative source behind a symlink
  remains rejected.
- Project-local generated dependencies are unavailable inside the candidate;
  verification must not silently bind them from the owner tree.

## Operational notes

`fam-os-natural-dev.service` is active on `localhost:8877` from the current
checkout. The older service on `127.0.0.1:8765` was not changed.

## Recommended next entry point

Retry the same natural analysis prompt. For mutation, load the signed
`fam-os-userns` profile first, then verify the project through a release-owned
Node/TypeScript recipe or explicit integration environment.
