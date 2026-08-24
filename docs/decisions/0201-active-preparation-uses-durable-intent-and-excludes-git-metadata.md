# ADR 0201: Active preparation uses durable intent and excludes Git metadata

Status: Accepted

## Context

Restart-safe engineering cannot infer intent, workspace, tool, network, Git, or
acceptance scope from a task ID. Candidate cloning of a repository must also not
copy mutable `.git` internals into a model-editable workspace.

## Decision

Every product task starts from an `EngineeringTaskDefinition` containing the
exact `EngineeringTaskEnvelope`, acceptance-policy identity, creation time, and
canonical digest. SQLite persists the definition and initial loop state in one
transaction. Product admission checks task lifetime and every workspace,
authority, toolchain, network, registry, Git, and resource bound against the
active task-scoped grant.

The active preparation orchestrator derives its repository query from durable
intent, observes the exact canonical Git workspace under fixed file/context
bounds, treats repository text as untrusted context, invokes the bounded planner,
and creates an isolated candidate. The receipt-driven driver advances each
stage in one optimistic database commit after all three concrete outputs exist.
Candidate creation failure leaves the loop at `requested`; unreferenced
candidate storage is safe to reconcile separately. Symbolic links are rejected.

Candidate snapshots exclude `.git` entirely. Candidate operations and previews
explicitly reject any path entering `.git`; local Git operations remain behind
the dedicated Git adapter.

## Consequences

- Restart can recover exact task intent rather than asking a model to reconstruct
  authority.
- Console and Shell projections show intent, workspace, and acceptance policy.
- Repository instructions remain untrusted evidence.
- Model-editable candidate content cannot include Git credentials, hooks, refs,
  config, or object storage.
- Active implementation, verification, repair, apply, and delivery orchestration
  are still required to complete Phase 30.

## Evidence

- `src/fam_os/core/engineering/task_definition.py`
- `src/fam_os/core/engineering/preparation.py`
- `src/fam_os/adapters/filesystem/repository_evidence.py`
- `src/fam_os/adapters/filesystem/candidate_workspace.py`
- `src/fam_os/product/engineering_loop_api.py`
- `tests/unit/test_engineering_preparation_orchestrator.py`
- `tests/unit/test_product_engineering_loop_api.py`

## Superseded decisions

None.
