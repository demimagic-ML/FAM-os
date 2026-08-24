# Handoff 0254: Natural SQLite database engineering

**Date:** 2026-07-19  
**Plan step:** Phase 27.12 and installed portions of 30.1/30.5  
**Status:** Partial  
**Previous handoff:** `0253-natural-runtime-diagnostic-composition.md`

## Objective

Attach real SQLite migration engineering to the natural-language master loop,
including deterministic planning, rollback rehearsal, candidate-only effects,
encrypted recovery, exact changeset evidence, independent owner post-apply
observation, commit, restart reconstruction, and history-preserving rollback.

## Scope completed

- Added deterministic database-intent recognition and exact single-target
  SQLite selection from repository evidence.
- Added strict forward/rollback migration-pair discovery with contiguous steps,
  digest binding, embedded-transaction denial, and bounded optional fixture
  inspection.
- Added disposable forward and reverse preflight under the production SQLite
  authorizer; rollback must restore exact baseline schema and data before a
  plan is accepted.
- Persisted the exact plan before candidate mutation and stored immutable
  owner-encrypted plan, backup, candidate verification, compensation, and
  post-apply evidence.
- Added fresh-authority recovery to `DatabaseEngineeringService` and replay-safe
  product reconciliation after an uncertain effect.
- Corrected database grant scope to the selected owner workspace while keeping
  every database effect isolated and identity-bound in the exact candidate.
- Added `DatabasePostapplyReceipt` and strict schema validation over owner-tree
  integrity, schema/data digests, and exact expected state.
- Allowed exact passing database evidence to satisfy candidate verification for
  database-only work and bound its receipt into the same changeset checkpoint.
- Included only the authorized binary database in the final diff while
  excluding private `.fam` journals and encrypted backups from candidate scans.
- Added database candidate and post-apply evidence to lifecycle, changeset,
  commit, restart reconstruction, Console, Shell, and natural task responses.
- Added a real temporary-Git integration scenario proving natural request,
  model-proposed reversible SQL, owner unchanged before approval, candidate
  mutation, encrypted backup/restore rehearsal, checkpoint, apply, owner
  observation, local commit, restart-safe evidence, and inverse-commit rollback.

## Explicitly not completed

- PostgreSQL and MySQL engineering adapters and their service/network/opaque
  secret composition.
- A newly built and installed signed release proving the natural database path.
- Independently enforced `compat-cpu-16gb` and
  `full-reference-workstation` database rows.
- Host AppArmor policy installation, final aggregate qualification, 24-hour
  soak, and independent human review.

## Architecture and decisions

ADR 0219 makes reverse rehearsal a planning requirement, separates candidate
database evidence from independent owner post-apply evidence, and keeps remote
database engines behind the Phase 27.13 environment boundary. Database-only
verification is permitted only from an exact typed passing database receipt;
it does not waive any other applicable gate.

`src/fam_os/product/natural_engineering_execution.py` remains above the
project's preferred 300-line target because it already owns the bounded
generation/repair/checkpoint sequence and this change had to preserve one
atomic lifecycle. The new database responsibilities are decomposed into three
separate files below 300 lines; a later orchestration extraction must preserve
the established receipt order and restart semantics.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/database/sqlite_planning.py` | Deterministic target, migration, fixture, and reverse-rehearsal planner |
| `src/fam_os/adapters/database/sqlite_sql.py` | Shared strict SQL statement splitting and transaction-control denial |
| `src/fam_os/adapters/database/sqlite_fixtures.py` | Bounded fixture-manifest inspection |
| `src/fam_os/adapters/sqlite/engineering_database.py` | Immutable owner-encrypted database lifecycle store |
| `src/fam_os/core/engineering/database.py` | Strict database post-apply receipt contract |
| `src/fam_os/core/engineering/master_loop.py` | Database candidate/post-apply evidence transitions |
| `src/fam_os/product/database_engineering_api.py` | Plan-before-effect, recovery, and owner re-observation facade |
| `src/fam_os/product/natural_engineering_execution.py` | Natural candidate database composition and checkpoint binding |
| `src/fam_os/product/natural_engineering_api.py` | Post-apply database gate, commit evidence, and reconstruction |
| `src/fam_os/product/candidate_changeset_api.py` | Authorized binary database changeset inclusion |
| `src/fam_os/console/http.py` | Owner-scoped read-only database evidence endpoint |
| `src/fam_os/shell/engineering_loop_contracts.py` | Strict database evidence query operation |
| `tests/integration/test_natural_database_engineering.py` | Real full-lifecycle SQLite proof |
| `tests/unit/test_natural_database_planning.py` | Deterministic planning and hostile SQL denial |

## Public interfaces

New interfaces are `NaturalSQLitePlanBuilder`,
`SQLiteDatabaseEngineeringStore`, `StoredDatabaseEngineeringResult`,
`ProductDatabaseEngineeringApi`, `DatabasePostapplyReceipt`, master-loop
database verification/reverification transitions, Console route
`GET /api/v1/engineering/tasks/{task_id}/database`, and Shell operation
`database`. `squash_candidate_edits` adds explicit
`authorized_external_paths` for receipt-backed non-edit outputs.

The contract catalog now contains 414 schema roots, including
`fam.core.database-postapply-receipt`.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_natural_database_planning tests.unit.test_database_engineering tests.unit.test_database_engineering_service tests.unit.test_database_engineering_composition tests.unit.test_sqlite_database_engineering_adapter tests.integration.test_installed_database_authority_chain tests.integration.test_natural_database_engineering tests.unit.test_candidate_workspace tests.unit.test_candidate_squash tests.unit.test_candidate_changeset_service tests.unit.test_product_engineering_loop_api tests.integration.test_natural_engineering_checkpoint tests.integration.test_natural_runtime_diagnostics tests.integration.test_console_engineering_loop tests.unit.test_fam_shell_engineering_loop_transport tests.unit.test_shell_engineering_projection tests.unit.test_natural_engineering_execution tests.unit.test_product_natural_engineering_api tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests -q"
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: the affected natural/database/lifecycle/Console/Shell/contract suite
passed 94 tests, and the architecture suite passed 41 tests. The full source
discovery executed 1,825 tests with 16 failures, 5 errors, and 2 skips. The
five errors are the existing order-sensitive Shell `core_unavailable` group;
the failures are in optional MCP and the existing production
verifier/remote/gateway paths that remain downstream of the unavailable host
sandbox boundary. No database or new natural-lifecycle test failed.

Full logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-18-24-823Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-18-24-824Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-18-43-573Z.log`

## Evidence and artifacts

- `tests/integration/test_natural_database_engineering.py`
- `tests/unit/test_natural_database_planning.py`
- `docs/decisions/0219-natural-sqlite-engineering-requires-rehearsed-rollback-and-owner-postapply-proof.md`
- `artifacts/engineering/phase27/database-authority-installed-20260719-attempt3.json` (historical installed authority baseline only)

## Known limitations and risks

- The natural adapter supports local candidate SQLite only; remote database
  engines have materially different authority and secret boundaries.
- Fixture declaration and shape are bounded, but fixture contents remain
  untrusted input and are executed only inside the disposable/candidate
  database under the SQLite authorizer.
- Source execution cannot substitute for the required new signed installed
  and independently enforced profile evidence.
- The local host identity is composition-derived and must stay stable across a
  task; final multi-host qualification must bind the installed device identity.

## Operational notes

No live service, active release, owner repository, host policy, database,
secret, package, port, or external system was changed. The integration test
used temporary candidate and Git workspaces and removed them on exit.

## Recommended next entry point

Compose PostgreSQL and MySQL database engineering with Phase 27.13's service,
network, backup, and opaque-secret lifecycle. Start from ADR 0219,
`src/fam_os/product/database_engineering_api.py`, and the integration
environment contracts; retain the exact natural checkpoint and post-apply
receipt sequence.
