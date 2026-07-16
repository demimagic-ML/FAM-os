# Handoff 0020: Unified profile-driven benchmark composition

**Date:** 2026-07-16  
**Plan step:** Phase 2.12  
**Status:** Complete  
**Previous handoff:** `0019-dual-validation-profiles.md`

## Objective

Make the existing activation, verified, routing, and policy parity workloads run through one profile-driven service composition in either the constrained CPU compatibility mode or the full-workstation accelerator mode, without duplicating orchestration or retaining a hidden 16 GiB benchmark ceiling.

## Scope completed

- Added `BenchmarkComposition`, which admits one strict `ValidationProfileDocument` and one strict `EffectiveResourceBudget` only when they name the same profile and the budget stays within the service envelope.
- Derived legacy placement inputs from the admitted effective budget instead of hard-coded CPU, RAM, or GPU values.
- Added a complete report constraints payload containing profile and budget identity, service limits, effective CPU/RAM/VRAM/storage authority, headroom, and accelerator visibility.
- Added one `ProfiledOllamaService` lifecycle path for both named profiles.
- Translated provider-neutral service limits to provider-neutral lifecycle `ResourceLimits` before the systemd adapter boundary.
- Kept Ollama-specific accelerator-denial variables in the provider adapter: compatibility mode hides CUDA/Vulkan and selects the CPU library; full mode does not inject accelerator-disabling variables.
- Removed the separate `CpuOllamaService` implementation and `tools/parity/cpu_service.py`.
- Required `--profile` and `--effective-budget` in all four parity entrypoints.
- Updated activation, verified-quality, routing, and policy reports to identify their decoded profile, admitted budget, and derived constraints.
- Generalized placement and resource checks so CPU compatibility evidence and accelerator-capable full-host evidence use the same check implementation.
- Added contract, adapter, admission, CLI-signature, and regression tests.
- Added the operations protocol, ADR 0021, Master Plan evidence, and this handoff.

## Explicitly not completed

- No live `DiscoveredResourceState` or `EffectiveResourceBudget` was captured for the reference workstation; that is Phase 2.13.
- No service was started and no model was loaded or transferred in this phase.
- No benchmark inference was executed on the RTX 5080 or CPU.
- No claim is made yet that requested systemd limits, GPU visibility, or placement were actually applied on the live machine.
- CPU utilization, VRAM time series, model-transfer bytes, SSD I/O, and foreground responsiveness are not yet captured by the current cgroup observer.

## Architecture and decisions

ADR 0021 makes profile plus effective budget the benchmark admission boundary. The profile describes reusable policy and service authority; the effective budget is the discovery-clamped allocation for one captured host. A workload cannot choose CPU/GPU behavior independently from those documents.

The service implementation is intentionally singular. Compatibility and full mode differ through decoded `ServiceResourceEnvelope` data. Provider-specific Ollama environment settings remain at the adapter edge and do not enter scheduler or schema contracts.

An absent full-profile `memory_max_bytes` means no artificial profile ceiling. It does not mean execution may ignore discovered capacity, cgroup state, scheduler headroom, or the admitted effective budget.

The four workload tools still adapt the new composition to the earlier `ResourceBudget` placement interface. This preserves one workload implementation while Phase 3 replaces remaining legacy orchestration boundaries.

## Files changed

| Path | Purpose |
|---|---|
| `tools/parity/composition.py` | Strict profile/budget admission and report/placement derivation |
| `tools/parity/profile_service.py` | One profile-driven Ollama lifecycle service path |
| `tools/parity/cpu_service.py` | Deleted obsolete CPU-only service fork |
| `tools/parity/checks.py` | Profile-aware placement and resource evidence checks |
| `tools/run_activation_parity.py` | Required shared composition and profile-derived report constraints |
| `tools/run_verified_parity.py` | Required shared composition and profile-derived report constraints |
| `tools/run_routing_parity.py` | Required shared composition and profile-derived report constraints |
| `tools/run_policy_parity.py` | Required shared composition and profile-derived report constraints |
| `tests/unit/test_profiled_benchmark_composition.py` | Admission, derivation, adapter, and common-entrypoint tests |
| `docs/operations/PROFILED_BENCHMARKS.md` | Inputs, commands, translation, and evidence rules |
| `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md` | Phase 2.12 consumer and implementation status |
| `docs/decisions/0021-unified-profile-driven-benchmark-composition.md` | Unified composition decision |
| `README.md` | Current implementation and next-step status |
| `MASTER_PLAN.md` | Phase 2.12 completion and Phase 2.13 entry point |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0020-profile-driven-benchmark-composition.md` | This implementation record |

## Public interfaces

- `BenchmarkComposition`
- `load_benchmark_composition`
- `ProfiledServiceSettings`
- `ProfiledOllamaService`

All four workload CLIs now require:

```text
--profile PATH
--effective-budget PATH
```

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_profiled_benchmark_composition \
  tests.unit.test_parity_tooling
```

Result: all 12 focused tests passed; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 248 FAM_OS tests passed; 0 failures. The previous suite contained 239 tests.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 35 generated schemas matched and Python compilation completed successfully.

Each parity entrypoint completed `--help` successfully. A source scan found no remaining `CpuOllamaService`, `CpuServiceSettings`, `tools.parity.cpu_service`, or hard-coded 16 GiB benchmark limit under `tools/`.

An AST audit found no implementation module at or above 300 lines and no function at or above 50 lines.

## Evidence and artifacts

- `docs/operations/PROFILED_BENCHMARKS.md`
- `docs/decisions/0021-unified-profile-driven-benchmark-composition.md`
- `tests/unit/test_profiled_benchmark_composition.py`
- `configs/profiles/compat-cpu-16gb.json`
- `configs/profiles/full-reference-workstation.json`

Phase 2.12 produced architectural and deterministic test evidence only. It intentionally produced no live workstation benchmark artifact.

## Known limitations and risks

- A full run requires a fresh, strict, privacy-reviewed effective budget; Phase 2.13 must create it from live discovery.
- A `ServiceDefinition` proves requested lifecycle intent, not that systemd/cgroup/device policy applied it.
- Full mode has no artificial `MemoryMax`; fresh discovery, cgroup observation, explicit headroom, and budget admission are therefore mandatory.
- Provider environment translation is still an Ollama adapter responsibility and must be verified against the running service.
- The current cgroup observer records RAM, swap, events, and pressure, but not CPU utilization, VRAM, SSD I/O, or model transfers.
- Accelerator activation checks depend on loaded-model residency telemetry and cannot prove device placement before a model is loaded.
- Historical Phase 1 artifact commands do not contain the newly required profile/budget arguments; they remain historical evidence, not current rerun instructions.
- Workload names retain their Phase 1 parity terminology even though their composition boundary is now Phase 2.
- No application weaving, UI, or expert-quality expansion was exercised by this infrastructure change.

## Operational notes

This phase changed Python tools, tests, documentation, and generated-input consumption only. It did not mutate system services, cgroups, models, storage, accelerator settings, or external applications.

## Recommended next entry point

Begin Phase 2.13. Capture a privacy-reviewed live `DiscoveredResourceState`, compose and persist the full effective budget, and add a bounded full-workstation smoke harness that records verified quality, CPU, RAM, VRAM, model transfers, SSD I/O, latency, and structured failures. Never infer missing measurements: record a metric as unavailable with its reason until an observer can measure it.
