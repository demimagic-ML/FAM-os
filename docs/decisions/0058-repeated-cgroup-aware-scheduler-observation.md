# ADR 0058: Use repeated inclusive cgroup observations for scheduler admission

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The composed resource budget contains capture-time utilization but cannot safely
drive later placement. CPU use is cumulative in cgroup v2, managed service
children are already included in their parent scope, and missing GPU/cache
telemetry could otherwise look like free capacity. The two named profiles also
need the same runtime mechanism without forcing this workstation into the 16 GiB
CPU-only policy.

## Decision

Publish `fam.scheduler.live-resources/v1alpha1` and construct it from repeated
samples of one FAM-owned cgroup scope. Treat the inclusive scope memory as the
admission source and retain children only for attribution. Derive CPU utilization
only from linked cumulative-counter samples and reject mismatched scope/budget or
non-increasing time.

Clamp live CPU and memory authority by both the immutable effective budget and
lower current cgroup ceilings. Preserve headroom before schedulable capacity.
When only child memory is available, retain the measured usage but expose zero
admissible headroom.

Represent unknown accelerator and cache usage as unknown rather than zero. An
allowed missing accelerator and any missing budgeted cache are degradation. A
policy-disabled, zero-budget accelerator needs no telemetry for admission.
Observe NVIDIA memory/utilization through the bounded existing query and cache
bytes through bounded, no-symlink configured-directory traversal.

## Consequences

- Parent and child memory cannot be double-counted.
- First samples are honest baselines; later samples prove interval CPU load.
- Missing admission-critical telemetry fails closed without discarding unrelated
  valid measurements.
- Compatibility and full-host profiles share code but retain different GPU
  placement authority and memory ceilings.
- NPU runtime telemetry is not faked; Phase 7.8 owns that investigation.
- The strict schema catalog increases from 51 to 52 roots.

## Alternatives considered

1. Reuse capture-time discovered state: rejected because it becomes stale.
2. Sum child cgroups: rejected because a parent scope already includes children.
3. Treat absent telemetry as zero usage: rejected because it invents capacity.
4. Read host-wide RAM only: rejected because it cannot prove FAM scope ceilings.
5. Degrade for every disabled device: rejected because admission is already
   impossible and this would prevent a complete CPU-only profile observation.

## Evidence

- `src/fam_os/scheduler/live_contracts.py`
- `src/fam_os/scheduler/live_sampler.py`
- `src/fam_os/adapters/linux/live_resources.py`
- `schemas/v1alpha1/fam.scheduler.live-resources.schema.json`
- `tests/unit/test_live_resource_sampler.py`
- `tests/unit/test_linux_live_resources.py`
- `artifacts/scheduler/phase7.1/`
