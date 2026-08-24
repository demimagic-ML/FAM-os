# Handoff 0198: Bounded master engineering loop

**Date:** 2026-07-18  
**Plan step:** Phase 30  
**Status:** Complete  
**Previous handoff:** `0197-controlled-git-and-remote-publication.md`

## Objective

Compose engineering evidence, approvals, mutation, verification, Git, and
publication into one persistent authority-forgetting lifecycle.

## Scope completed

- Added strict lifecycle stages and one monotonic multidimensional budget.
- Added optimistic SQLite WAL persistence and hash-chained revisions.
- Added multiple changeset checkpoints and distinct publication checkpoints.
- Cleared pending mutation/publication authority on restart.
- Added dependency/design auxiliary evidence and Console projection.
- Added declared self-hosted source modification, verification, apply, restore.

## Explicitly not completed

- Phase 31 24-hour soak and independent human security review.

## Architecture and decisions

ADR 0173 makes restart authority-forgetting and monotonic budgets durable
properties rather than UI conventions.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/master_loop.py` | Lifecycle and budget policy |
| `src/fam_os/adapters/sqlite/engineering_loop.py` | Revisioned durability |
| `src/fam_os/console/engineering.py` | Read-only task view |
| `tests/unit/test_master_engineering_loop.py` | Lifecycle/restart/budget tests |
| `tests/integration/test_self_hosted_source_modification.py` | Source-only self-update fixture |

## Public interfaces

`EngineeringLoopBudget`, `EngineeringLoopState`, `EngineeringLoopStage`,
`MasterEngineeringLoop`, `SQLiteEngineeringLoopStore`, and
`EngineeringConsoleView`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_master_engineering_loop tests.integration.test_self_hosted_source_modification -v
```

Result: three lifecycle tests pass, including restart invalidation, budget
exhaustion, and self-hosted apply/restore.

## Evidence and artifacts

- `docs/decisions/0173-master-engineering-loop-is-revisioned-and-authority-forgetting.md`
- Installed suite evidence in `artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt2.json`

## Known limitations and risks

- Operational proof remains intentionally unavailable until Phase 31's soak and
  independent human review are complete.

## Operational notes

SQLite stores use WAL and full synchronous commits; close adapters cleanly.

## Recommended next entry point

Continue Phase 31 from ADR 0174, the adversarial ledger, and signed runner.
