# Handoff 0008: Verified code orchestration

**Date:** 2026-07-16  
**Plan step:** Phase 1.9  
**Status:** Complete  
**Previous handoff:** `0007-python-verifier-sandbox.md`

## Objective

Rebuild the parent prototype's route, economical generation, verification, bounded repair, scheduler-selected eviction, escalation, and safe release behavior as small provider-neutral application modules without copying `run_verified_task` or allowing any failed candidate into the user-visible result.

## Scope completed

- Added typed routing requests and results plus a `TaskRouter` port.
- Moved the proven four-route prompt and deterministic JSON/loose-response parser into routing policy.
- Added `ModelTaskRouter` over `InferenceRuntime`; it contains no Ollama transport behavior.
- Added `ExpertCatalog` and `PlacementPlanner` ports so Core does not own model identity or eviction choice.
- Tightened `PlacementPlan` validation for empty and duplicate eviction IDs.
- Split Core execution into generation settings, policy, prompt builders, one-attempt execution, placement execution, evidence contracts, and a bounded coordination use case.
- Preserved the parent sequence: economical attempt, economical repair, escalation using failure feedback, and escalation repair.
- Used scheduler context allocation for every expert inference request.
- Resolved every planned eviction before unloading any runtime model, preventing a missing catalog entry from causing a known partial unload.
- Halted on verifier `ERROR`; infrastructure failure is not sent to an expert as code-repair feedback.
- Retained every candidate, metric, and verification report in internal `ExecutionAttempt` evidence.
- Enforced the release invariant: only a final passing verification creates a verified `TaskResult` with content.
- Added 16 focused tests, increasing the FAM_OS suite from 77 to 93 tests.
- Added ADR 0008 and updated component ownership, root status, master-plan evidence, and handoff navigation.

## Explicitly not completed

- No production expert catalog, registry, manifest loader, or placement algorithm was added; Phase 6 and Phase 7 own those systems.
- No complete memory, swap, device, or cgroup enforcement was added. Phase 1.9 consumes the scheduler's context allocation and unload decisions only.
- No live Ollama/Bubblewrap orchestration run or performance claim was made; Phase 1.10 owns measured parity.
- No kernel, math, retrieval, or application-action execution use case was added.
- No CLI, FAM Shell, local API, report serializer, persistence layer, or external schema was added.
- No cancellation, concurrency, deadline, total token budget, or global repair/escalation cost budget was added.
- No structured conversion of unexpected router, runtime, planner, unload, or verifier exceptions was added; Phase 2 and Phase 4 own general degradation contracts.
- The parent `rnf/orchestrator.py`, configs, scripts, tests, and historical artifacts were not modified.

## Architecture and decisions

ADR 0008 establishes four responsibilities:

1. Routing converts a provider-neutral `RoutingRequest` into `RoutingResult`. `ModelTaskRouter` may call `InferenceRuntime`, but it cannot allocate resources or execute the selected route.
2. Experts resolve stable expert IDs through `ExpertCatalog`. Core policy refers to IDs rather than hard-coded model names.
3. The scheduler chooses `PlacementPlan`, including context and evictions. `PlacementExecutor` validates and executes that plan but cannot add an eviction.
4. Core coordinates bounded state transitions and owns the final `TaskResult` release decision. `AttemptExecutor` performs exactly one inference and one verification; it contains no retry or escalation policy.

`VerifiedExecutionOutcome` is trusted internal orchestration evidence and can contain failed candidates. `TaskResult` is the user-visible release contract and cannot contain content for withheld or failed states. Future APIs and telemetry exporters must preserve this distinction rather than serializing the complete outcome to an untrusted client.

Verifier `FAILED` means the candidate may be repaired within policy bounds. Verifier `ERROR` means the acceptance authority did not operate correctly, so execution stops with a failed result. A non-code route is withheld by this code-specific use case without activating an expert.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/routing/contracts.py`, `ports.py` | Routing request, result, and router port |
| `src/fam_os/routing/prompts.py`, `parsing.py`, `inference.py` | Proven route prompt, deterministic parser, and model-backed router policy |
| `src/fam_os/routing/__init__.py`, `README.md` | Public exports and ownership |
| `src/fam_os/experts/ports.py`, `__init__.py`, `README.md` | Expert catalog lookup boundary |
| `src/fam_os/scheduler/contracts.py` | Stronger placement eviction validation |
| `src/fam_os/scheduler/ports/placement.py`, `ports/__init__.py` | Placement planner boundary |
| `src/fam_os/scheduler/README.md` | Placement decision versus execution ownership |
| `src/fam_os/core/execution/contracts.py` | Attempt kinds, terminal statuses, attempt evidence, and outcome invariants |
| `src/fam_os/core/execution/policy.py` | Bounded generation, repair, and escalation policy data |
| `src/fam_os/core/execution/prompts.py` | Pure initial and repair prompt construction |
| `src/fam_os/core/execution/attempt.py` | One inference plus one verification |
| `src/fam_os/core/execution/placement.py` | Scheduler-plan validation and runtime eviction execution |
| `src/fam_os/core/execution/use_case.py`, `__init__.py` | Verified code state transitions and public exports |
| `src/fam_os/core/README.md` | Internal evidence and user release boundary |
| `tests/unit/execution_fakes.py` | Reusable runtime, router, verifier, catalog, and planner fakes |
| `tests/unit/test_routing_policy.py` | Route parser and model-router request tests |
| `tests/unit/test_execution_helpers.py` | Prompt bounds, safe eviction, and scheduled context tests |
| `tests/unit/test_verified_code_execution.py` | Transition, bound, eviction, halt, and release-safety tests |
| `docs/decisions/0008-verified-code-orchestration-boundary.md` | Durable orchestration and release decision |
| `README.md`, `MASTER_PLAN.md`, `handoffs/README.md` | Current status, Phase 1.9 evidence, and handoff sequence |
| `.codebase-memory/graph.db.zst`, `.larry/` | Refreshed codebase discovery artifacts |

## Public interfaces

- `RoutingRequest`
- `RoutingResult`
- `TaskRouter`
- `ModelRouterSettings`
- `ModelTaskRouter`
- `parse_route_decision(content, request)`
- `RouteParseError`
- `ExpertCatalog`
- `PlacementPlanner`
- `AttemptKind`
- `ExecutionAttempt`
- `ExecutionStatus`
- `VerifiedExecutionOutcome`
- `GenerationSettings`
- `VerifiedCodePolicy`
- `AttemptExecutor`
- `CandidateGenerationError`
- `PreparedPlacement`
- `PlacementExecutor`
- `PlacementExecutionError`
- `VerifiedCodeExecution`

These are source-level Python interfaces. `ExecutionAttempt` and `VerifiedExecutionOutcome` are trusted internal evidence contracts; `TaskResult` remains the external release-safe object.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests
```

Result: 93 tests passed in 0.006 seconds, 0 failures.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests
```

Result: all 10 parent RNF tests passed in 0.026 seconds, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 212 files indexed, 29 artifacts written, verification clean.

The codebase knowledge graph was refreshed in fast mode with 1,430 nodes and 5,477 edges. It found `VerifiedCodeExecution`, `AttemptExecutor`, `PlacementExecutor`, `ModelTaskRouter`, `TaskRouter`, `PlacementPlanner`, and `ExpertCatalog`. The outbound trace from `VerifiedCodeExecution.execute` reaches the router port and decomposed economical, repair, placement, attempt, and terminal-result methods. Graph-augmented search found no parent `rnf` import under `FAM_OS/src/` and no provider/process implementation string in Core, routing, experts, or scheduler code.

The largest FAM_OS implementation file is `core/execution/use_case.py` at 252 lines, below the 300-line target. Graph inspection reports its public `execute` method at 20 lines and the largest new execution method at 26 lines, below the 50-line target.

## Evidence and artifacts

- `docs/decisions/0008-verified-code-orchestration-boundary.md`
- `tests/unit/test_verified_code_execution.py`
- Refreshed `.codebase-memory/graph.db.zst`
- Refreshed `.larry/` repository map

The exhausted-path test runs economical, repair, escalation, and escalation-repair attempts with four failed reports. It confirms that all four candidates remain in internal evidence while `TaskResult.status` is `WITHHELD` and `TaskResult.content` is `None`.

## Known limitations and risks

- Only the code route has an execution use case.
- `ExpertCatalog` and `PlacementPlanner` have test fakes but no production implementation yet.
- Full placement budgets are not enforced; only context allocation and model eviction are consumed.
- Multiple unloads are not transactional. All expert IDs are resolved before the first unload, but a runtime failure during the unload sequence can still leave partial eviction.
- Unexpected port exceptions currently propagate unless they are the explicit empty-generation, missing-expert, or placement-resolution errors handled by the use case.
- There is no deadline or aggregate token, memory, energy, or repair cost budget across attempts.
- Model-produced failure evidence remains untrusted even when included in a repair prompt.
- Internal outcomes contain raw candidates and must not be exposed wholesale through future client APIs.
- Routing loose-text recovery is compatibility behavior; exact JSON remains the intended model contract.
- No live orchestration parity or reference-machine measurement was run in this change.

## Operational notes

All orchestration tests used in-memory fakes. No live model was loaded or unloaded, no verifier subprocess was launched, no service was started, and no system configuration changed. Larry used `npx` to refresh local discovery artifacts. The codebase graph artifact was regenerated for the shared workspace.

## Recommended next entry point

Begin Phase 1.10 by reading `docs/migration/PROTOTYPE_MIGRATION_MAP.md`, `evaluations/routing_tasks.jsonl`, the parent `rnf/benchmark.py`, `rnf/expert_experiment.py`, `scripts/run-policy-comparison`, and the canonical `artifacts/benchmarks/verified-task-20260716-104128.json`.

First create a parity matrix listing every required parent test and measured report field. Then add small FAM-owned benchmark or hardware-test entry points that compose the migrated public ports. Start with the 24-task routing benchmark, preserve raw artifacts, and only then run constrained activation, three-policy residency comparison, and the real verified 7B-to-14B escalation. Do not introduce a production registry or unversioned configuration shortcut merely to run the parity harness.
