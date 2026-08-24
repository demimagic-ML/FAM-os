# ADR 0168: Repository intelligence consumes untrusted adapter evidence

Status: Accepted

## Context

Full engineering work requires repository-wide mapping, semantic search,
symbols, references, diagnostics, manifests, dependencies, Git state, and
architecture instructions. Those sources come from replaceable tools and from
repository-controlled bytes. Neither a language server nor an `AGENTS.md` file
may become a Core authority source. Long analysis also needs restart-safe,
bounded progress without turning a shell script into the runtime.

## Decision

Core owns `BoundedRepositoryPlanner`. It consumes a versioned
`RepositoryEvidenceBundle` through `RepositoryEvidenceAdapter`; it does not
open a workspace or invoke LSP, Tree-sitter, code-graph, compiler-database,
editor, or Git implementations directly. Source-kind metadata preserves which
adapter produced each observation.

Every repository context record and architecture rule is permanently labelled
`untrusted_context`. Generated files and dependency metadata retain source and
role metadata. Typed evidence is bounded by counts and total text bytes and
must declare that no mutation occurred. Planner output binds request, task,
bundle, workspace revision, and a deterministic evidence digest.

Architecture proposals must decide modules, interfaces, schemas, migrations,
ADRs, dependency direction, security boundaries, rollout, and acceptance
criteria exactly once. They identify affected tests and require a pre-mutation
checkpoint. Proposal and analysis contracts reject mutation claims.

Engineering task progress uses typed graph and event contracts behind an
`EngineeringTaskGraphRepository` port. The filesystem adapter stores canonical
schema documents in an owner-private append-only JSONL log with a global SHA-256
record chain and `fsync`. Replay rejects duplicate JSON keys, partial final
records, sequence conflicts, changed hashes, increasing budgets, incomplete
dependencies, invalid checkpoints, and post-terminal events.

## Consequences

- Repository tools can be replaced without changing Core planning policy.
- Malicious instructions, comments, generated code, and package metadata can
  inform analysis but cannot grant authority or mutate policy.
- An unfamiliar repository can be traced and designed without mutation.
- The JSONL adapter is suitable component evidence, not yet an encrypted
  multi-process production database; installed wiring remains later work.
- Architecture completeness is structurally checkable rather than left to
  prose convention.

## Alternatives considered

- Let Core call language servers or Git commands directly: rejected because it
  couples policy to concrete tools and their response formats.
- Trust repository instruction files as policy: rejected because repository
  authors and dependencies control those bytes.
- Store only the latest task snapshot: rejected because restart diagnosis and
  checkpoint history require append-only evidence.
- Use a shell script as the long-running planner: rejected because scripts are
  not the runtime or an authority boundary.

## Evidence

- `src/fam_os/core/engineering/repository/`
- `src/fam_os/adapters/filesystem/engineering_task_graph.py`
- `tests/unit/test_repository_intelligence.py`
- `tests/contract/schema_repository_fixtures.py`
- `schemas/v1alpha1/fam.core.repository-evidence.schema.json`
- `schemas/v1alpha1/fam.core.architecture-proposal.schema.json`

## Superseded decisions

None. This extends the Core/adapters and untrusted-model boundaries without
weakening ADRs 0165–0167.
