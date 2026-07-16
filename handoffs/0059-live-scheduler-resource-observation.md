# Handoff 0059: Live scheduler resource observation

**Date:** 2026-07-16  
**Plan step:** Phase 7.1  
**Status:** Complete  
**Previous handoff:** `0058-reference-expert-packages.md`

## Objective

Replace capture-time resource assumptions with strict repeated cgroup-aware
scheduler observations, and prove the same mechanism against the real
compatibility and full-reference workstation profiles.

## Scope completed

- Published strict `fam.scheduler.live-resources/v1alpha1` contracts.
- Added linked baseline/complete/degraded observation sequencing.
- Derived normalized CPU utilization from repeated cumulative cgroup samples.
- Clamped scheduler CPU/RAM authority by both the composed budget and lower live
  cgroup ceilings while preserving memory headroom.
- Made the FAM scope cgroup authoritative and retained child readings only for
  attribution, peak usage, cumulative CPU, and OOM kills.
- Made child-only memory fallback fail closed with zero admissible headroom.
- Represented unknown accelerator/cache usage as unknown rather than free.
- Added NVIDIA `gpu-N` memory/utilization and bounded, no-symlink cache-directory
  adapters behind replaceable ports.
- Added contract, sampler, adapter, degraded-source, profile, and regression tests.
- Captured fresh privacy-reviewed budgets and two live samples for each named
  profile using CPU-active transient user services.
- Retained the initial NPU-classification diagnostic and captured corrected
  canonical baseline-to-complete evidence.

## Explicitly not completed

- Context-memory estimation is Phase 7.2.
- Expert residency states, admission, and eviction are Phase 7.3-7.4.
- SSD mmap/page-cache and I/O attribution are Phase 7.7; this step accounts only
  configured FAM cache file bytes.
- Intel NPU telemetry and placement remain Phase 7.8. The currently discovered
  NPU has zero placement budget and is not represented as usable.

## Architecture and decisions

ADR 0058 makes a repeated inclusive FAM scope the scheduler's decision-time
source. Inventory remains physical identity; the effective budget remains
authority; the live observation supplies current usage and availability. A
missing admission-critical source fails closed. A missing policy-disabled
zero-budget accelerator does not degrade an otherwise complete observation.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/live_contracts.py` | Strict repeated observation domain contract. |
| `src/fam_os/scheduler/live_ports.py` | Accelerator/cache observation ports and readings. |
| `src/fam_os/scheduler/live_sampler.py` | Cgroup-aware repeated sampler and capacity derivation. |
| `src/fam_os/adapters/linux/live_resources.py` | NVIDIA and bounded cache adapters. |
| `src/fam_os/schemas/catalog.py` | Registers the 52nd strict root. |
| `tools/run_live_resource_smoke.py` | Live profile-specific evidence capture. |
| `tests/unit/test_live_resource_sampler.py` | Sampling and fail-closed regressions. |
| `tests/unit/test_linux_live_resources.py` | Adapter boundary and traversal tests. |
| `tests/contract/schema_scheduler_fixtures.py` | Strict schema round-trip fixture. |
| `docs/protocols/LIVE_SCHEDULER_RESOURCE_OBSERVATION.md` | Protocol and evidence guide. |
| `docs/decisions/0058-repeated-cgroup-aware-scheduler-observation.md` | Durable scheduler decision. |

## Public interfaces

- `LIVE_RESOURCE_OBSERVATION_VERSION`
- `SchedulerResourceObservation`, `ObservationStatus`
- `LiveCpuAvailability`, `LiveMemoryAvailability`
- `LiveAcceleratorAvailability`, `LiveStorageAvailability`
- `ManagedServiceUsage`, `LiveResourceSampler`
- `AcceleratorRuntimeObserver`, `StorageRuntimeObserver`
- `NvidiaAcceleratorRuntimeObserver`
- `CacheDirectory`, `DirectoryStorageRuntimeObserver`
- `fam.scheduler.live-resources/v1alpha1`
- `tools/run_live_resource_smoke.py`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 -m compileall -q src tests tools
python3 <AST implementation file/function size gate>
python3 <canonical dual-profile raw summary gate>
systemctl --user list-units 'fam-live-resources-*' --all --no-legend --no-pager
larry index
codebase-memory-mcp index_repository full
```

Result: both Python environments passed 612 tests with three expected
environment-dependent skips. All 52 strict schemas and compileall passed. The
size gate checked 356 source/tool Python files and found no file above 300 lines
and no function above 50 lines. Canonical compatibility/full samples each moved
from baseline to complete, linked their IDs, recorded respective nonzero CPU
deltas of 523,977 and 523,975 microseconds, used authoritative cgroup memory,
had no degradation reasons, and ended inactive with no matching unit left. The
compatibility GPU placement flag was false; full-reference GPU placement was
true. Larry refreshed 953 files / 2,695 symbols to 15,835 nodes / 52,419 edges.
The independent code graph refreshed to 16,151 nodes / 53,717 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.1/compat-profile/20260716T172121776125Z/`
- `artifacts/scheduler/phase7.1/full-profile/20260716T172125249397Z/`
- `artifacts/scheduler/phase7.1/compat-observations-canonical/`
- `artifacts/scheduler/phase7.1/full-observations-canonical/`
- `artifacts/scheduler/phase7.1/compat-observations/` (retained diagnostic)
- `artifacts/scheduler/phase7.1/full-observations/` (retained diagnostic)
- `schemas/v1alpha1/fam.scheduler.live-resources.schema.json`
- `docs/decisions/0058-repeated-cgroup-aware-scheduler-observation.md`

## Known limitations and risks

- Cgroup CPU is normalized against effective quota and capped at one; later
  pressure policy may need an explicit saturation duration.
- Cache traversal is exact for configured regular files but does not yet measure
  mapped resident pages or block-device I/O.
- Scope fallback retains known child usage but deliberately admits no new memory.
- A cgroup parse/invariant error still fails the sample rather than converting
  corrupt telemetry into a degradation guess.

## Operational notes

No model was loaded, downloaded, modified, or deleted. Live services ran direct
`dd` CPU work with profile-derived CPU/RAM/swap/task limits, then were stopped
and removed. The initial diagnostic observation directories are historical
failed evidence and should remain append-only.

## Recommended next entry point

Begin Phase 7.2 context-memory estimation. Read this handoff, live observation
contracts, expert resource requirements/runtime bindings, inference request
token settings, and Ollama residency evidence. Define provider-neutral context
components and estimation confidence before changing placement policy.
