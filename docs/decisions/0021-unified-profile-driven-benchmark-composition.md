# ADR 0021: One benchmark composition path for compatibility and full-host modes

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The Phase 1 parity tools used `CpuOllamaService`, injected four CPU-forcing environment variables, set a 16 GiB memory ceiling in code, and repeated those constraints in each report. Adding a separate GPU service and separate full-host workloads would duplicate orchestration and make comparisons drift.

The new profile documents and effective budgets already contain the required provider-neutral authority. Benchmark tools need one admitted composition that can translate those values at the adapter edge without moving Ollama or systemd details into Scheduler or Core.

## Decision

All routing, activation, residency-policy, and verified-escalation workloads require one `BenchmarkComposition` containing a strict `ValidationProfileDocument` and matching strict `EffectiveResourceBudget`.

Admission verifies profile identity and the service memory, swap, CPU, and accelerator-visibility envelope. Legacy per-expert `ResourceBudget` values are derived from the effective scheduler budget rather than fixed at 16 GiB.

`ProfiledOllamaService` is the only benchmark service composition. It builds the same provider-neutral `ServiceDefinition` lifecycle path for both profiles. CPU mode adds accelerator-disabling environment only at the Ollama adapter edge. Full mode does not inject those disabling variables. Service RAM/swap/CPU become `ResourceLimits` consumed by the existing systemd adapter.

Every workload CLI accepts the same `--profile` and `--effective-budget` inputs. Every report obtains constraints from the same composition and names both source documents. The historical workload, prompt, routing, verification, and release code remains shared and unchanged.

## Consequences

- CPU and GPU modes cannot drift into separate workload programs.
- Full-host runs are no longer silently forced through CPU environment or a 16 GiB code constant.
- The same profile/budget mismatch and envelope checks protect every workload.
- Reports expose CPU, RAM, VRAM, storage, and service constraints consistently.
- Existing Phase 1 artifacts remain historical evidence, but new CLI runs require explicit profile and effective-budget inputs.
- Phase 2.13 must capture the live discovery/budget artifact before a full run; test fixtures are not publishable machine evidence.
- Provider environment translation remains in benchmark adapter composition, not public scheduler policy.

## Alternatives considered

1. Add `GpuOllamaService`: rejected because separate services would duplicate lifecycle and readiness behavior.
2. Keep hard-coded 16 GiB placement/report values while only changing service environment: rejected because reports and policy would lie in full-host mode.
3. Infer the profile from GPU presence: rejected because discovery is not authority and the CPU baseline must remain runnable on a GPU host.
4. Let each workload load profiles independently: rejected because admission and reporting would drift.
5. Put Ollama environment variables in profile JSON: rejected because provider settings are adapter details.
6. Auto-build a full budget from host RAM only: rejected because cgroups, headroom, GPU, storage, and current pressure are required inputs.

## Evidence

- `tools/parity/composition.py`
- `tools/parity/profile_service.py`
- Updated `tools/run_*_parity.py` entrypoints
- `tests/unit/test_profiled_benchmark_composition.py`
- `docs/operations/PROFILED_BENCHMARKS.md`
- ADR 0011, ADR 0019, and ADR 0020
