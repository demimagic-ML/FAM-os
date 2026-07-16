# Handoff 0021: Privacy-reviewed full-workstation smoke baseline

**Date:** 2026-07-16  
**Plan step:** Phase 2.13  
**Status:** Complete  
**Previous handoff:** `0020-profile-driven-benchmark-composition.md`

## Objective

Capture this reference workstation through strict privacy-reviewed Phase 2 resource documents and run one bounded full-capability workload through the unified profile path while recording verified quality, CPU, RAM, VRAM, model transfers, SSD I/O, latency, and failures without weakening verification or mislabeling unavailable measurements.

## Scope completed

- Extended the existing cgroup-v2 observer with CPU time and aggregated `io.stat` counters while retaining unavailable values as `None`.
- Extended stable parity serialization with CPU and I/O evidence.
- Added bounded NVIDIA resource sampling for index, model, capacity, usage, utilization, and driver without GPU UUID or PCI identity.
- Added a privacy-reviewed mapper from the read-only Linux hardware adapter into strict `HostInventory` and `DiscoveredResourceState` documents.
- Replaced hostname, mount/device paths, PCI identity, and accelerator paths with opaque capture, `gpu-N`, `npu-N`, and `storage-root` identities.
- Added a strict capture CLI that persists host inventory, discovered state, effective budget, composed decisions, and a privacy review in one unique artifact directory.
- Composed the checked `full-reference-workstation` profile against the live machine state.
- Added root-partition Linux block-I/O sampling as a labeled fallback when delegated user cgroups do not expose `io.stat`.
- Added fresh-service before/after evidence for cgroup CPU/RAM/swap/events/pressure, NVIDIA VRAM, loaded-model residency transfers, and storage counters.
- Added a full-workstation smoke CLI over the same verified workload and `ProfiledOllamaService` path introduced in Phase 2.12.
- Scrubbed resolved local input paths from distributable smoke reports; filenames are retained for reproduction.
- Added a FAM-owned bounded smoke fixture and retained every failed diagnostic run.
- Produced the canonical privacy-scrubbed raw report `workstation-smoke-20260716-114418-717004.json`.
- Added tests, operations documentation, ADR 0022, Master Plan closure, and this handoff.

## Captured workstation and budget

- CPU: 24 visible logical CPUs, 22 schedulable, 2 reserved.
- RAM: 67,017,834,496 bytes physical; 54,132,932,608 bytes schedulable; 12 GiB explicit headroom.
- GPU: NVIDIA GeForce RTX 5080, 17,094,934,528 bytes VRAM; 14,958,067,712 scheduler bytes; 1 GiB reserve.
- Storage: 2,013,991,550,976-byte NVMe root tier; 551,365,922,816 bytes available at capture; 275,682,961,408 scheduler cache bytes; 100 GiB free-space reserve.
- Service: no artificial RAM maximum, discovered accelerators visible, zero service swap.

These values belong to capture `20260716T113113568743Z`; available memory/storage and current usage are time-varying and must not be reused as fresh discovery.

## Canonical smoke result

The canonical report contains seven attempts: 7B economical generation plus two repairs, followed by 14B escalation plus three repairs. All seven candidates failed deterministic verification. The terminal result was `withheld`, `verified` was false, and no candidate content was released.

The report recorded:

- service CPU usage: 25,036,818 microseconds;
- service memory peak: 665,387,008 bytes, separate from accelerator residency;
- service swap: zero;
- OOM kills: zero;
- 14B final model residency/accelerator residency delta: 9,470,098,799 bytes;
- observed GPU-memory delta: 9,813,622,784 bytes;
- maximum of the two GPU samples: 11,174,674,432 bytes;
- host-root-window storage delta: 8,749,056 read bytes and 68,214,784 written bytes;
- inference wall/load/token-rate metrics for every attempt;
- deterministic failure stage, reason, and bounded verifier evidence for every attempt.

The smoke evidence-category checks all passed except `verified_quality`. Therefore `smoke_checks.passed` is false. This is a complete failed-quality baseline, not a passing quality claim.

## Architecture and decisions

ADR 0022 makes privacy minimization part of the adapter boundary. Raw host identity is not needed for scheduling and therefore does not enter serialized resource evidence.

Service cgroup counters remain the preferred attribution source. This workstation's user service cgroup exposed CPU, memory, swap, pressure, and events but not `io.stat`. The fallback root-partition counter is explicitly scoped to all host activity during the benchmark window. It cannot be used for billing, enforcement, or per-service I/O claims.

Model transfers are recorded as fresh-service residency deltas, not PCI-bus transfer measurements. The fresh service had no loaded models before the workload and reported the final model's resident and accelerator bytes afterward.

Verification is an invariant. Multiple installed experts were diagnostically tried, but no failed candidate was reclassified as quality. The canonical fixture retains the 7B-to-14B path and the failed result so later Expert Fabric work has an honest fitness baseline.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/contracts.py` | CPU and I/O resource snapshot fields |
| `src/fam_os/adapters/cgroup/parsing.py` | Pure CPU and aggregate I/O counter parsers |
| `src/fam_os/adapters/cgroup/observer.py` | Extended cgroup-v2 observation |
| `src/fam_os/adapters/linux/nvidia.py` | Privacy-safe live NVIDIA resource readings |
| `src/fam_os/adapters/linux/resource_discovery.py` | Privacy-reviewed strict state mapping |
| `src/fam_os/adapters/linux/block_io.py` | Root-storage I/O fallback |
| `tools/parity/serialization.py` | CPU and I/O report serialization |
| `tools/workstation/capture.py` | Strict live capture and budget composition |
| `tools/workstation/evidence.py` | Fresh-service workstation evidence collector |
| `tools/capture_workstation_resources.py` | Capture CLI |
| `tools/run_workstation_smoke.py` | Full smoke CLI |
| `tools/run_verified_parity.py` | Optional evidence collection and path privacy scrub |
| `configs/benchmarks/full-workstation-verified-smoke.json` | Bounded FAM-owned smoke workload |
| `tests/fixtures/cgroup/.../cpu.stat` | CPU parser fixture |
| `tests/fixtures/cgroup/.../io.stat` | I/O parser fixture |
| `tests/unit/test_linux_block_io.py` | Storage parser/discovery tests |
| `tests/unit/test_linux_resource_discovery.py` | Privacy mapping tests |
| `tests/unit/test_workstation_evidence.py` | Evidence delta/availability tests |
| `tests/unit/test_cgroup_observer.py` | Extended cgroup observer coverage |
| `tests/unit/test_linux_nvidia.py` | NVIDIA resource parsing coverage |
| `docs/operations/FULL_WORKSTATION_SMOKE.md` | Capture, provenance, result, and reproduction |
| `docs/decisions/0022-privacy-reviewed-full-workstation-evidence.md` | Privacy and measurement-scope decision |
| `artifacts/workstation/20260716T113113568743Z/` | Strict capture and raw diagnostic/canonical reports |

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 257 FAM_OS tests passed in 0.191 seconds; 0 failures. The previous suite contained 248 tests.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 35 generated schemas matched and compilation completed successfully.

An AST audit found no implementation module at or above 300 lines and no function at or above 50 lines.

Strict capture documents were decoded during composition. A canonical-file scan found no home path, username, user-cgroup identifier, block-device path, or PCI bus address. After the canonical run, `fam-parity-ollama.service` reported `inactive/dead`, an empty control group, and `Result=success`.

## Evidence and artifacts

- Capture directory: `artifacts/workstation/20260716T113113568743Z/`
- Canonical report: `workstation-smoke-20260716-114418-717004.json`
- Strict budget: `effective-budget.json`
- Strict discovery: `discovered-state.json`
- Privacy review: `privacy-review.json`
- Human interpretation: `docs/operations/FULL_WORKSTATION_SMOKE.md`
- Decision: ADR 0022

Earlier reports in the capture directory are immutable diagnostic evidence from telemetry and expert-selection development. Reports created before path scrubbing are local-only and noncanonical.

## Known limitations and risks

- The canonical quality gate failed. Phase 4 expert registration/fitness and Phase 11 evaluation must improve this without weakening trusted tests.
- Root-partition SSD deltas include unrelated host activity and are not service-exclusive.
- VRAM uses two boundary samples rather than a high-frequency time series; `max_observed` is only the maximum of those samples.
- Loaded-model residency delta is evidence of a fresh-service load, not a direct PCI transfer counter.
- Physical CPU core topology is not yet included in the privacy-reviewed inventory; the scheduler uses logical CPUs.
- Current CPU pressure in the effective budget is zero because discovery does not yet take an interval-based `/proc/stat` sample.
- The generic full profile sees an NPU device node but has no vendor capacity telemetry, so its scheduler budget remains zero.
- Service cgroup memory does not include all driver-owned GPU memory; RAM and VRAM must remain separate evidence dimensions.
- No thermal, power, long-duration, application-weaving, or foreground responsiveness test was run in Phase 2.13.

## Operational notes

All capture probes were read-only. Benchmark runs used installed local models and did not download, delete, or modify model data. Each run used a fresh user-scoped transient service on port 11435, enforced zero service swap, and stopped the service on exit. The existing main Ollama service was not replaced.

## Recommended next entry point

Begin Phase 3.1. Define the FAM Supervisor capability boundary and non-goals using the already migrated `ServiceLifecycle`, `ResourceLimits`, `ServiceStatus`, and `ResourceSnapshot` contracts as evidence. Separate current user-systemd capabilities from future privileged operations; do not broaden privileges merely because Phase 2 now has live hardware evidence.
