# ADR 0062: Constrain the compatibility service rather than falsifying host capacity

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The compatibility profile runs on a 64 GiB host but must prove behavior inside a
16 GiB ceiling. An earlier composition guard compared host-effective memory with
the service envelope, rejecting a valid bounded service whenever the host was
larger. Shrinking captured host facts would make resource evidence untruthful.

## Decision

Keep discovered host/effective capacity intact. Require scheduler memory plus
the explicit reserve to fit the 16 GiB service envelope, apply that envelope via
the isolated service cgroup, and use live cgroup observations as the admission
scope. Apply the effective scheduler CPU quota when the profile does not declare
a smaller service-specific quota.

Make Phase 7.5 pass only through a strict report proving simultaneous CPU-only
multi-expert residency, zero VRAM, zero swap, zero OOM kills, an operating-system
reserve, explicit Laguna/Gemma rejection, durable unload, and inactive cleanup.

## Consequences

- The minimum-machine test is real even when executed on a stronger host.
- Host capacity evidence remains truthful and reusable by the full profile.
- The scheduler receives all 23 currently schedulable logical CPU cores instead
  of an accidental unbounded or artificially reduced CPU setting.
- Strong models are not quality-downgraded; they are honest compatibility-profile
  rejections and remain full-profile Phase 7.6 candidates.
- The strict schema catalog increases from 58 to 59 roots.

## Alternatives considered

1. Rewrite host effective memory as 16 GiB: rejected because it falsifies
   discovery and makes full-profile comparison unreliable.
2. Remove the composition guard: rejected because scheduler plus reserve could
   then exceed the enforced service ceiling.
3. Execute only one small model: rejected because it does not prove multi-expert
   scheduling or concurrent residency.
4. Load Laguna/Gemma and rely on OOM behavior: rejected because deterministic
   admission must prevent unsafe activation before provider mutation.

## Evidence

- `src/fam_os/scheduler/baseline_contracts.py`
- `tools/parity/composition.py`
- `tools/parity/profile_service.py`
- `tools/cpu_baseline/workload.py`
- `tools/run_cpu_only_baseline.py`
- `tests/integration/test_cpu_only_baseline_evidence.py`
- `artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/`
