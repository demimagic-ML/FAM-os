# ADR 0219: Natural SQLite engineering requires rehearsed rollback and owner post-apply proof

Status: Accepted

## Context

Phase 27.12 already had strict database contracts, a real candidate SQLite
adapter, encrypted backups, restart reconciliation, Core authorization, and a
signed installed authority fixture. That path still required a caller to
construct the database plan and invoke the database service separately from a
natural engineering task. It therefore could not contribute trusted evidence
to the ordinary changeset checkpoint, owner apply, post-apply verification, or
Git delivery lifecycle.

Database work also differs from ordinary source edits. The candidate contains
a mutable binary database and private recovery state, while the model proposes
untrusted SQL text. Treating the binary as a generated file, exposing recovery
metadata in a diff, or accepting candidate verification as proof of the owner
database would weaken the existing authority and evidence boundaries.

## Decision

Core deterministically recognizes database intent and admits exactly one
workspace-relative SQLite target. It accepts only complete ordered
forward/rollback migration pairs, verifies every source digest, rejects
embedded transaction control, and validates any bounded synthetic fixture
manifest. Before a plan can authorize a candidate effect, the planner applies
the forward migrations to a disposable copy under the same SQLite authorizer,
checks every expected schema digest, executes rollback in reverse, and demands
exact baseline schema and data restoration.

The owner grant remains scoped to the selected owner workspace because that is
the resource the owner authorized FAM to change. The concrete effect remains
isolated in the task's exact candidate workspace and is additionally bound to
the candidate identity, database path, plan digest, trusted host identity, and
changeset. Planning persists before effect. Execution obtains fresh live
`EXECUTE` and `MODIFY` decisions, and uncertain execution invokes the existing
recovery adapter only with newly minted authority. A completed attempt is
replayed from immutable owner-encrypted evidence rather than executed twice.

The successful candidate database receipt is a trusted verification input for
a database-only task. The final changeset may include the exact changed binary
database only when it is authorized by the selected plan and receipt. Private
`.fam` attempt journals, encrypted backups, and other recovery evidence are
excluded from candidate scans and cannot enter the owner changeset.

After checkpoint approval and transactional changeset apply, Core independently
reopens the owner database and emits a strict post-apply receipt binding the
task, plan, target, changeset, candidate receipt, integrity result, and exact
schema/data digests. The lifecycle reaches `REVERIFIED` and Git commit only
when this receipt and every other applicable verifier, diagnostic,
documentation, and review gate pass. History-preserving rollback continues to
use the normal changeset journal and inverse commit.

PostgreSQL and MySQL remain remote-service work. They must be composed with
Phase 27.13 environment, network, and opaque-secret controls rather than
receiving a local SQLite shortcut.

## Consequences

- A natural-language SQLite request now uses the same grant, candidate,
  budget, checkpoint, apply, reverify, commit, restart, and rollback lifecycle
  as ordinary source work.
- Forward success alone is insufficient: exact reverse rehearsal is a planning
  prerequisite, and owner-tree observation is a post-apply prerequisite.
- The model can propose SQL assets but cannot choose a target, engine, host,
  authorization, changeset, verification result, or recovery action.
- A database-only task does not need an unrelated language toolchain solely to
  cross candidate verification.
- Source composition does not qualify the signed installed product, either
  hardware profile, PostgreSQL/MySQL, the soak, or human review. Phase 27.12
  remains open.

## Alternatives considered

- Apply model-generated SQL directly to the owner database: rejected because
  it bypasses candidate isolation, exact review, and rollback rehearsal.
- Treat a successful candidate receipt as post-apply proof: rejected because
  it does not observe the owner workspace after the approved transaction.
- Put encrypted backups in the user-visible changeset: rejected because
  private recovery evidence is not a deliverable and may contain sensitive
  database bytes.
- Reuse the local SQLite path for remote databases: rejected because service
  identity, network, credential, backup, and compensation boundaries differ.

## Evidence

- `src/fam_os/adapters/database/sqlite_planning.py`
- `src/fam_os/adapters/database/sqlite_sql.py`
- `src/fam_os/adapters/sqlite/engineering_database.py`
- `src/fam_os/product/database_engineering_api.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/product/natural_engineering_api.py`
- `src/fam_os/core/engineering/database.py`
- `src/fam_os/core/engineering/master_loop.py`
- `tests/unit/test_natural_database_planning.py`
- `tests/integration/test_natural_database_engineering.py`

