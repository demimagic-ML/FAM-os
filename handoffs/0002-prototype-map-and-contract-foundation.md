# Handoff 0002: Prototype map and contract foundation

**Date:** 2026-07-16  
**Plan step:** Phase 1.1 through 1.4  
**Status:** Complete  
**Previous handoff:** `0001-project-foundation.md`

## Objective

Begin FAM_OS implementation without copying the coupled RNF experiment modules. Inventory the complete parent prototype, assign every proven behavior to a component, create the package boundaries, and define the typed interfaces required before Ollama, Linux, or systemd code moves.

## Scope completed

- Inventoried every indexed parent module, config, evaluation, script, test, benchmark artifact, hardware artifact, and public behavior.
- Wrote the controlled migration order, destination owners, coupling risks, and parity gates.
- Created the independent `fam-os` Python project with `src/` package layout.
- Created all planned component packages with local ownership and non-goal READMEs.
- Added immutable request, final-result, routing, expert, scheduler, verification, inference, and telemetry contracts.
- Added a provider-neutral inference runtime port for the future Ollama adapter.
- Enforced the invariant that withheld and failed results cannot expose candidate content.
- Recorded the component contract and dependency decision in ADR 0002.
- Added 14 focused unit tests and confirmed the 10 parent prototype tests still pass.

## Explicitly not completed

- No hardware profiling behavior has moved yet; that is Phase 1.5.
- No Ollama, systemd, cgroup, verifier, or orchestration implementation was copied.
- No service was started, stopped, installed, or enabled.
- No models were loaded, unloaded, downloaded, or benchmarked.
- External serialization schemas and compatibility rules remain Phase 2 work.

## Architecture and decisions

ADR 0002 establishes component-owned provider-neutral contracts rather than a global contracts module. Core owns requests, results, and application ports; domain components own their own language; adapters will implement ports without introducing provider fields into those contracts.

The first safety invariant is executable in `TaskResult`: `WITHHELD` and `FAILED` cannot contain content, while `VERIFIED` must agree with `verified=True`. This preserves the prototype behavior that incorrect intermediate candidates never become final output.

## Files changed

| Path | Purpose |
|---|---|
| `pyproject.toml` | Independent FAM_OS package boundary and `src/` discovery |
| `src/fam_os/core/contracts/` | Task request and final result contracts |
| `src/fam_os/core/ports/` | Provider-neutral inference runtime port |
| `src/fam_os/routing/` | Four-route decision contract |
| `src/fam_os/experts/` | Expert tier, lifecycle, capability, and descriptor contracts |
| `src/fam_os/scheduler/` | Resource budget and placement plan contracts |
| `src/fam_os/verification/` | Deterministic verification report contract |
| `src/fam_os/telemetry/` | Inference measurement contract |
| `src/fam_os/{supervisor,adapters,registry,memory,connectors}/` | Package boundaries and local ownership rules |
| `tests/unit/` | Fourteen contract and invariant tests |
| `docs/migration/PROTOTYPE_MIGRATION_MAP.md` | Complete source-to-component inventory and parity plan |
| `docs/decisions/0002-provider-neutral-contract-boundaries.md` | Contract ownership and dependency ADR |
| `README.md` | Current implementation status and next step |
| `MASTER_PLAN.md` | Phase 1.1 through 1.4 completion and Phase 1.5 entry point |

## Public interfaces

- `TaskRequest`
- `ResultStatus` and `TaskResult`
- `RouteName` and `RouteDecision`
- `ExpertTier`, `ExpertState`, and `ExpertDescriptor`
- `ResourceBudget` and `PlacementPlan`
- `VerificationStatus` and `VerificationReport`
- `InferenceMetrics`
- `MessageRole`, `InferenceMessage`, `InferenceRequest`, `InferenceResponse`, `LoadedModel`, and `InferenceRuntime`

These are Python contracts for controlled migration. They are not yet external wire schemas.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 14 tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 parent prototype tests passed, including the sandbox verifier tests.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -c "from fam_os.core.contracts import TaskRequest; from fam_os.core.ports import InferenceRuntime; from fam_os.routing import RouteName; print(TaskRequest('smoke', 'hello').request_id, RouteName.CODE.value, InferenceRuntime.__name__)"
```

Result: `smoke code InferenceRuntime`.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 91 files indexed, 36 artifacts written, verification clean.

The codebase knowledge graph was also refreshed in fast mode. A graph lookup found all nine queried contract and test symbols under `FAM_OS/`, confirming the new source structure is discoverable.

All Python implementation files are 66 lines or fewer; no god module or script was introduced.

## Evidence and artifacts

- `docs/migration/PROTOTYPE_MIGRATION_MAP.md`
- `docs/decisions/0002-provider-neutral-contract-boundaries.md`
- Parent `EXPERIMENT_RESULTS.md`
- Parent `artifacts/benchmarks/verified-task-20260716-104128.json`

## Known limitations and risks

- Contracts are source-level Python APIs; serialized schema versions and compatibility policy are not defined yet.
- The initial contracts may need additive fields as real adapters reveal missing facts. Breaking changes require an ADR and updated tests.
- No adapter parity has been demonstrated yet.
- `TaskResult` enforces terminal release shape, but future core use cases must still choose `WITHHELD` whenever required verification fails.
- The parent artifact inventory reflects the index at this handoff date and must be refreshed before Phase 1.11.

## Operational notes

This change is package and test scaffolding only. It did not touch the parent implementation, start the constrained Ollama service, or mutate machine configuration. Rollback consists of removing this Phase 1 slice; no external state requires cleanup.

## Recommended next entry point

Start Phase 1.5. Read `AGENTS.md`, `MASTER_PLAN.md`, this handoff, ADR 0002, `docs/migration/PROTOTYPE_MIGRATION_MAP.md`, and parent `rnf/profile.py`. First add a typed hardware-profile contract and fixture tests, then implement a read-only Linux adapter that reproduces the parent fields without serialization or CLI concerns.
