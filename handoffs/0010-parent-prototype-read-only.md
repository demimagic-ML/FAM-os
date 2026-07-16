# Handoff 0010: Parent prototype read-only

**Date:** 2026-07-16  
**Plan step:** Phase 1.11  
**Status:** Complete  
**Previous handoff:** `0009-phase1-measured-parity.md`

## Objective

Close controlled prototype migration after measured parity by making `FAM_OS/` the only active implementation, retaining the parent RNF tree as runnable historical evidence, and automatically preventing active FAM_OS code and tools from importing parent implementation modules.

## Scope completed

- Added a root repository rule declaring the parent RNF implementation and its associated fixtures, scripts, tests, measurements, and research documents frozen.
- Added a dedicated read-only marker with the exact frozen paths, exception policy, and canonical Phase 1 evidence.
- Added an archive banner to the parent README while preserving all historical reproduction commands.
- Added an AST-based architecture test that scans every Python file under `FAM_OS/src` and `FAM_OS/tools`.
- Rejected direct `import rnf`, `from rnf...`, and constant-string `__import__` or `import_module` dependencies.
- Verified that active FAM_OS source and parity tools contain zero parent implementation imports.
- Added ADR 0010 to make the product/evidence boundary durable.
- Marked Master Plan step 1.11 complete and updated the migration map and project entry points.
- Re-ran all FAM_OS and parent tests after the freeze and refreshed both project indexes.

## Explicitly not completed

- No parent implementation, configuration, evaluation, script, test, or benchmark artifact was deleted or modified.
- No filesystem permissions were changed; the prototype remains runnable for comparison and reproduction.
- No live Ollama, systemd/cgroup, Bubblewrap, routing, policy, or verified-escalation experiment was repeated because Phase 1.11 changes repository policy, documentation, and an architecture test only. Canonical live results remain in handoff 0009.
- No Phase 2.1 schema work was started.
- No compatibility promise was added between the `rnf` Python namespace and FAM_OS.

## Architecture and decisions

ADR 0010 establishes one active product tree and one frozen evidence tree. New behavior belongs under `FAM_OS/`; the parent is read-only unless the user explicitly requests isolated historical maintenance.

The freeze is policy-based instead of enforced with `chmod`. This preserves tests, packaging, and reproduction while root `AGENTS.md`, the README banner, and `PROTOTYPE_READ_ONLY.md` make ownership unambiguous to both humans and agents.

Documentation alone is insufficient for dependency direction. `ParentPrototypeBoundaryTests` parses Python syntax rather than relying on a text pattern, covers both product source and development/parity tools, and rejects static plus constant-string dynamic imports rooted at `rnf`. Tests may compare historical outputs, but active code cannot obtain behavior by importing prototype modules.

## Files changed

| Path | Purpose |
|---|---|
| `../AGENTS.md` | Root rule defining the frozen prototype and explicit maintenance exception |
| `../README.md` | Archive banner and historical-reproduction framing |
| `../PROTOTYPE_READ_ONLY.md` | Canonical frozen-path marker and closure evidence |
| `tests/architecture/__init__.py` | Architecture-test discovery package |
| `tests/architecture/test_no_parent_imports.py` | AST-enforced dependency boundary and marker check |
| `docs/decisions/0010-parent-prototype-retirement.md` | Canonical retirement decision |
| `docs/migration/PROTOTYPE_MIGRATION_MAP.md` | Complete/frozen migration status |
| `MASTER_PLAN.md` | Phase 1.11 completion and handoff evidence |
| `README.md` | Controlled migration completion and Phase 2.1 entry point |
| `handoffs/README.md` | Handoff 0010 sequence entry |
| `handoffs/0010-parent-prototype-read-only.md` | Final Phase 1 closure record |

## Public interfaces

No runtime API changed.

The repository-level interface changed as follows:

- `FAM_OS/` is the canonical product implementation.
- Parent RNF paths listed in `PROTOTYPE_READ_ONLY.md` are read-only evidence.
- Active Python under `FAM_OS/src` and `FAM_OS/tools` must not import `rnf`.
- Historical prototype maintenance requires an explicit user request and remains isolated from FAM_OS.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Result: 105 tests passed in 0.026 seconds, including both prototype-boundary tests; 0 failures.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 frozen parent tests passed in 0.025 seconds; 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tools tests
```

Result: completed successfully with no syntax or bytecode compilation errors.

Graph-augmented code search over `^FAM_OS/(src|tools)/` for direct and constant-string dynamic `rnf` imports returned 0 grep matches and 0 graph results. The AST test is the authoritative enforcement and passed over the same active roots.

Final discovery refresh: Larry indexed 257 files and 499 symbols, producing a 2,335-node/7,174-edge map. The persisted codebase knowledge graph contains 2,591 nodes and 8,136 edges.

## Evidence and artifacts

- `../PROTOTYPE_READ_ONLY.md`
- `docs/decisions/0010-parent-prototype-retirement.md`
- `tests/architecture/test_no_parent_imports.py`
- `docs/migration/PHASE_1_PARITY_REPORT.md`
- `artifacts/parity/phase1-parity-20260716-095056-252893.json`
- `handoffs/0009-phase1-measured-parity.md`

## Known limitations and risks

- The read-only state is a repository rule, not an operating-system write lock; enforcement depends on agents and contributors honoring `AGENTS.md`.
- The automated boundary detects Python imports. A future non-Python runtime, subprocess call into parent scripts, copied implementation, or runtime path manipulation requires its own guard if introduced.
- Parent tests prove the frozen evidence is still runnable, not that both implementations will remain behaviorally synchronized after Phase 1.
- Phase 1 measured Granite routing and Python code escalation only; broader expert coverage remains future work.
- Phase 2 must replace frozen benchmark fixture compatibility readers with explicit, versioned schemas without turning historical formats into accidental public APIs.

## Operational notes

Phase 1.11 did not start services, invoke models, change model storage, or modify machine configuration. The live Phase 1.10 experiments were not repeated. `fam-parity-ollama.service` was already stopped after canonical measurement; see handoff 0009 for ports, cgroup limits, runtime version, and cleanup details.

No rollback is normally needed. If the user explicitly reopens historical maintenance, keep the change inside frozen parent paths, document why, rerun the 10 parent tests, and do not add a dependency from FAM_OS to `rnf`.

## Recommended next entry point

Begin Phase 2.1. Read `MASTER_PLAN.md`, ADRs 0002 through 0010, `src/fam_os/core/contracts/`, and the existing Application Fabric contracts. First inventory the request, route, capability, execution-plan, and final-result shapes already proven in Phase 1, then propose versioned schemas without changing runtime behavior or provider-neutral boundaries.
