# RNF Prototype Migration Map

**Plan steps:** 1.1 and 1.2  
**Inventory date:** 2026-07-16  
**Source root:** `<REPO_ROOT>`

**Migration status:** Complete and frozen on 2026-07-16. The canonical migrated report is `FAM_OS/artifacts/parity/phase1-parity-20260716-095056-252893.json`; detailed interpretation is in `PHASE_1_PARITY_REPORT.md`, handoff 0009 records measured parity, and handoff 0010 records the parent read-only boundary. `FAM_OS/` is the active implementation.

## Migration rule

The parent RNF prototype is evidence, not a package to copy wholesale. Each proven behavior moves behind a FAM_OS-owned contract, receives focused parity tests, and only then replaces the parent entry point. The parent remains executable until Phase 1.10 establishes parity and Phase 1.11 marks it read-only.

## Public behavior inventory

| Prototype behavior | Evidence | FAM_OS owner | Required parity gate |
|---|---|---|---|
| Capture CPU, RAM, storage, GPU, NPU, OS, and Ollama facts | `rnf/profile.py` | `adapters/linux` with a hardware-profile contract | Fixture-based parsing plus a read-only local smoke test |
| Classify tasks into `kernel`, `code`, `math`, or `retrieval` | `rnf/benchmark.py` | `routing` | Existing route parser tests and 24-task benchmark schema |
| Call chat inference and collect load/token timing | Three RNF modules | `core/ports` plus `adapters/ollama` | Fake-runtime contract tests before live Ollama tests |
| List and unload resident models | `benchmark.py`, `expert_experiment.py`, `orchestrator.py` | `adapters/ollama` | Fake adapter tests plus live local smoke test |
| Enforce CPU-only 16 GiB/no-swap service policy | `scripts/rnf-cpu-server` | `supervisor` plus `adapters/systemd` and `adapters/cgroup` | Command construction tests and an opt-in hardware test |
| Inspect cgroup current, peak, limit, events, and pressure | `rnf/expert_experiment.py` | `adapters/cgroup` plus `telemetry` | Fixture tests for cgroup v2 files and systemd properties |
| Route, activate, optionally evict, and report an expert | `rnf/expert_experiment.py` | `core` use case, `experts`, and `scheduler` | End-to-end fake-runtime state-transition test |
| Compare fresh-service residency policies | `scripts/run-policy-comparison` | Small benchmark tool using supervisor and core APIs | Reproduce three policy reports on the reference profile |
| Extract and AST-sanitize generated Python | `rnf/verifier.py` | `verification/python` | Preserve all current unit tests and add adversarial cases |
| Run deterministic tests with namespace and resource limits | `rnf/verifier.py` | `verification/sandbox` plus supervisor adapter | Pass/fail/timeout/resource-limit security tests |
| Repair once, escalate from 7B to 14B, and release only passing output | `rnf/orchestrator.py` | Small `core` execution use cases | Failed candidates withheld; passing escalation released |
| Write versioned JSON experiment reports | All experiment modules | `telemetry` plus small tools | Schema validation and stable required fields |

## Python module inventory

| Source | Current responsibility | Destination | Migration treatment |
|---|---|---|---|
| `rnf/__init__.py` | Prototype package marker | `src/fam_os/__init__.py` | Replace; do not preserve the RNF namespace inside FAM_OS |
| `rnf/__main__.py` | Delegates to the prototype CLI | Future `fam_os.cli` package | Rebuild only when Phase 1 use cases have stable APIs |
| `rnf/cli.py` | Parses four commands and prints reports | Small CLI commands under `tools/` or `fam_os/cli/` | Split one command per module; CLI contains no policy |
| `rnf/benchmark.py` | Route taxonomy, prompt, parser, Ollama HTTP, metrics, benchmark loop, report writing | `routing`, `adapters/ollama`, `telemetry`, `tools/routing_benchmark` | Split by responsibility; keep the four-route parity set |
| `rnf/profile.py` | Reads Linux/proc/device facts and serializes a profile | `adapters/linux`, later hardware-profile schema | Move reads behind a hardware discovery port; keep serialization out of adapter |
| `rnf/expert_experiment.py` | Ollama client, inference metrics, cgroup reads, routing and expert activation | `adapters/ollama`, `adapters/cgroup`, `core`, `scheduler`, `telemetry` | Do not copy; this is the clearest prototype coupling hotspot |
| `rnf/verifier.py` | Code extraction, AST policy, sandbox construction, limits, execution, verdict serialization | `verification/python`, `verification/sandbox`, `telemetry` | Preserve behavior while separating policy from process execution |
| `rnf/orchestrator.py` | Runtime HTTP, prompts, routing, attempt loop, repair, eviction, escalation, verification, reporting | `core` use cases plus component ports | Replace with small route, execute, verify, repair, and escalate use cases |

## Configuration and evaluation inventory

| Source | Purpose | Destination and parity requirement |
|---|---|---|
| `configs/evaluation.json` | Three-model GPU-capable routing comparison | Versioned routing benchmark config; retain all model and generation controls |
| `configs/evaluation-cpu-16gb.json` | CPU-only Granite routing benchmark | Named `cpu-16gb` hardware profile overlay plus routing workload |
| `configs/expert-activation-cpu-16gb.json` | First 14B activation at 4K context | Historical experiment fixture; not a recommended runtime default |
| `configs/policy-persistent-14b.json` | Resident kernel plus 14B at 2K | Scheduler-policy fixture |
| `configs/policy-evict-14b.json` | Evict kernel before 14B at 2K | Scheduler-policy fixture |
| `configs/policy-persistent-7b.json` | Resident kernel plus 7B at 2K | Scheduler-policy fixture and initial preferred policy |
| `configs/verified-toposort-cpu-16gb.json` | Repair and 7B-to-14B verified escalation | Split expert policy, verifier manifest, task fixture, and runtime overlay |
| `evaluations/routing_tasks.jsonl` | 24 balanced routing cases | Routing evaluation package; preserve IDs, prompts, expected routes |
| `evaluations/verifiers/stable_topological_sort.py` | Trusted deterministic acceptance tests | Versioned verifier test bundle, never model-editable at runtime |

Configuration is currently unvalidated JSON with runtime, policy, workload, and trusted-test concerns mixed together. Phase 2 will assign schemas and layering; Phase 1 preserves the files as parity fixtures.

## Script and test inventory

| Source | Current behavior | Destination and gate |
|---|---|---|
| `scripts/rnf-cpu-server` | Start, stop, and inspect a transient CPU-only Ollama systemd user service | Supervisor commands over systemd/cgroup adapters; preserve explicit 16 GiB/no-swap controls |
| `scripts/run-policy-comparison` | Restart service and run three policy configs with cleanup | Small benchmark tool; preserve fresh-service isolation and cleanup |
| `tests/test_benchmark.py` | Route parsing, task loading, and summary tests | Routing unit tests plus benchmark-tool tests |
| `tests/test_verifier.py` | Extraction, AST safety, top-level stripping, pass/fail sandbox tests | Verification unit and security tests |

## Artifact inventory

Artifacts are immutable evidence and are not imported by runtime code. They will move or be copied only when the Phase 1.10 parity report is assembled.

| Artifact | Evidence represented | Future location |
|---|---|---|
| `artifacts/hardware-profile.json` | Reference host discovery snapshot | Hardware-test fixture with sensitive host fields redacted |
| `artifacts/benchmarks/kernel-routing-20260716-095504.json` | Initial multi-model route run | Historical routing evidence |
| `artifacts/benchmarks/kernel-routing-20260716-095900.json` | Follow-up route run | Historical routing evidence |
| `artifacts/benchmarks/expert-activation-20260716-100124.json` | Early expert activation | Historical activation evidence |
| `artifacts/benchmarks/expert-activation-20260716-100819.json` | Activation policy iteration | Historical activation evidence |
| `artifacts/benchmarks/expert-activation-20260716-100944.json` | Activation policy iteration | Historical activation evidence |
| `artifacts/benchmarks/expert-activation-20260716-102137.json` | Final three-policy comparison input | Historical scheduler evidence |
| `artifacts/benchmarks/verified-task-20260716-103155.json` | Early verified-task run | Historical verification evidence |
| `artifacts/benchmarks/verified-task-20260716-103715.json` | Verified-task iteration | Historical verification evidence |
| `artifacts/benchmarks/verified-task-20260716-104128.json` | Successful verified escalation | Canonical Phase 1 parity reference |

## Documentation and packaging inventory

| Source | Treatment |
|---|---|
| `RESIDENT_NEURAL_FABRIC.md` | Preserve as research thesis; architecture decisions move into FAM_OS ADRs |
| `EXPERIMENT_RESULTS.md` | Preserve as measured evidence; do not turn measurements into universal constants |
| `HANDOFF.md` | Preserve as prototype handoff; FAM_OS continuation uses numbered append-only handoffs |
| `README.md` | Preserve parent prototype reproduction instructions until parity |
| `pyproject.toml` | Keep parent package independent; FAM_OS owns its own `pyproject.toml` |
| `.gitignore` | Review when FAM_OS produces artifacts; do not silently broaden ignores during migration |

## Coupling to remove

1. Three separate HTTP clients currently encode Ollama behavior.
2. Routing response parsing and route taxonomy live inside a benchmark module.
3. Expert activation directly decides eviction and directly calls system tools.
4. Orchestration owns inference transport, prompts, retry policy, verification, and persistence.
5. Verification combines code policy, sandbox mechanism, process execution, and report serialization.
6. Configuration mixes trusted verifier inputs with model-editable task inputs.
7. Reports use untyped dictionaries whose required fields are implicit.

## Controlled migration order

1. Freeze the minimal provider-neutral contracts defined by ADR 0002.
2. Add Linux hardware profiling behind an adapter and prove profile parity.
3. Add one Ollama adapter implementing the inference runtime port.
4. Add systemd and cgroup adapters with no generative logic.
5. Split verifier policy from sandbox execution and reproduce the current tests.
6. Rebuild route, execute, verify, repair, and escalation as small core use cases.
7. Reproduce the recorded experiments, compare required fields and outcomes, then retire parent imports.

## Completion definition

This map is complete for Phase 1.1 and 1.2 when every indexed prototype source module, config, evaluation, script, test, and artifact has an explicit owner and a parity condition. Discovery should be rerun before Phase 1.11 in case the parent prototype changed during migration.
