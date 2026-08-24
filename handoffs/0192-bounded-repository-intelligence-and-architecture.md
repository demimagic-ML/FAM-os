# Handoff 0192: Bounded repository intelligence and architecture

**Date:** 2026-07-18  
**Plan step:** Phase 25.1–25.5 and Phase 25 exit gate  
**Status:** Phase 25 complete at contract and component-test maturity  
**Previous handoff:** `0191-owner-engineering-grants-and-assurance.md`

## Objective

Analyze an unfamiliar repository, trace its implementation path, identify
affected tests, and generate a decision-complete architecture proposal without
mutating the workspace, while preserving replaceable tool adapters and
restart-safe bounded progress.

## Scope completed

- Added bounded typed evidence for workspace files, retrieved context, semantic
  sources, symbols, references, diagnostics, manifests, dependencies, Git
  state, architecture rules, and observation limits.
- Added a replaceable `RepositoryEvidenceAdapter` boundary covering LSP,
  Tree-sitter, code graph, compiler database, editor API, Git, and existing
  workspace observations.
- Permanently classified repository instructions, comments/context, generated
  files, and dependency metadata as untrusted context or untrusted source roles.
- Added deterministic bounded relevance ranking, implementation-path traversal,
  affected-test discovery, and evidence digest binding.
- Added architecture proposals that must decide all nine required areas and
  require a pre-mutation checkpoint.
- Added typed bounded engineering task graphs, steps, budgets, termination
  conditions, checkpoints, and append-only events.
- Added an owner-private, hash-chained, `fsync`-backed JSONL repository that
  reloads across process instances and rejects tampering and partial records.
- Added six strict schema roots, compatibility tests, and cross-document
  identity validation.
- Passed the unfamiliar-repository exit scenario with zero mutations.

## Explicitly not completed

- No physical LSP, Tree-sitter, code-graph, compiler-database, editor, or Git
  adapter was installed or invoked; component tests use a replaceable fake.
- The JSONL graph repository is not yet encrypted or wired into the installed
  service.
- No repository mutation, candidate workspace, build, dependency installation,
  Git operation, or publication occurred.
- Phase 26 transactional workspace creation is not included.

## Architecture and decisions

ADR 0168 keeps observation mechanisms behind adapters and makes all
repository-derived text untrusted. Core owns bounds, tracing, architecture
completeness, and graph transition policy. The filesystem adapter only persists
and verifies canonical append-only events; it does not decide task policy.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/repository/contracts.py` | Repository evidence and untrusted-context contracts. |
| `src/fam_os/core/engineering/repository/planning.py` | Bounded Core analysis and architecture synthesis. |
| `src/fam_os/core/engineering/repository/digests.py` | Deterministic evidence identity. |
| `src/fam_os/core/engineering/repository/ports.py` | Replaceable observation and graph persistence ports. |
| `src/fam_os/core/engineering/repository/task_graph.py` | Typed task graph and transition policy. |
| `src/fam_os/adapters/filesystem/engineering_task_graph.py` | Restart-safe tamper-evident JSONL adapter. |
| `src/fam_os/schemas/catalog.py` | Registers six Phase 25 schemas. |
| `src/fam_os/schemas/references.py` | Validates repository analysis and graph references. |
| `tests/contract/schema_repository_fixtures.py` | Supplies unfamiliar-repository schema fixtures. |
| `tests/unit/test_repository_intelligence.py` | Proves trace, tests, design, no mutation, restart, bounds, and tamper rejection. |
| `docs/decisions/0168-repository-intelligence-consumes-untrusted-adapter-evidence.md` | Records the durable tool and trust boundary. |
| `MASTER_PLANv2.md` | Records Phase 25 completion evidence. |

## Public interfaces

- `RepositoryEvidenceBundle` and its typed nested evidence records
- `RepositoryAnalysisRequest`, `RepositoryAnalysis`, and
  `ImplementationPathStep`
- `ArchitectureArea`, `ArchitectureDecision`, and `ArchitectureProposal`
- `RepositoryEvidenceAdapter`
- `EngineeringTaskGraph`, `EngineeringTaskGraphEvent`, and related budget,
  step, state, and event enums
- `EngineeringTaskGraphRepository`, `EngineeringTaskGraphService`
- `JsonlEngineeringTaskGraphRepository`
- Six new exact-alpha schemas; 315 generated schemas total

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_contracts \
  tests.unit.test_engineering_grant_lifecycle \
  tests.unit.test_repository_intelligence \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references \
  tests.unit.test_action_intent_firewall \
  tests.unit.test_packaged_runtime_catalog \
  tests.unit.test_shell_engineering_projection \
  tests.unit.test_console_task_updates \
  tests.contract.test_integration_coverage
```

Result: 96 tests passed.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
git diff --check -- <Phase 24–25 source, configuration, tests, and documentation>
```

Result: all 315 generated schemas validated and the whitespace check passed.

The full-suite host dependency limitation remains recorded in Handoff 0188.

## Evidence and artifacts

- `docs/decisions/0168-repository-intelligence-consumes-untrusted-adapter-evidence.md`
- `tests/unit/test_repository_intelligence.py`
- `schemas/v1alpha1/fam.core.repository-analysis.schema.json`
- `schemas/v1alpha1/fam.core.architecture-proposal.schema.json`

## Known limitations and risks

- Fake adapter evidence proves the Core boundary, not compatibility with every
  real language server or code-graph implementation.
- Relevance ranking and traversal are deterministic and bounded but deliberately
  simple; semantic quality needs benchmark evidence before production claims.
- JSONL is single-host component persistence and currently lacks product
  encryption, multi-process coordination, archival compaction, and installed
  recovery UX.
- Proposal evidence references identify files but do not yet bind line spans or
  exact symbol-source bytes.

## Operational notes

Tests create only temporary owner-private JSONL files. No service, package,
model, credential, external repository, or operating-system state was changed.

## Recommended next entry point

Start Phase 26.1 with an adapter-owned copy-on-write candidate workspace from
an exact `WorkspaceSnapshot`. Read ADRs 0165, 0167, and 0168 plus Handoffs
0191–0192. Keep owner workspace mutation impossible until a coherent changeset
has passed candidate verification and the required checkpoint.
