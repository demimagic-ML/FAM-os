# ADR 0054: Profile-specific expert compatibility before placement

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Expert manifests declare architecture, resident/system memory, storage,
accelerator memory, and optional acceleration. FAM has separate physical host
inventory and effective budgets for the 16 GiB CPU baseline and full reference
workstation. A binary hardware check would conflate permanent incompatibility,
profile policy, current contention, and an optional GPU fallback.

## Decision

Introduce the strict `fam.expert.compatibility/v1alpha1` report and a pure
`ExpertCompatibilityEvaluator`. Evaluate one current manifest against one
consistent inventory/budget pair. Produce `compatible`,
`compatible_cpu_only`, `currently_constrained`, or `incompatible` with stable
layer-specific reason codes and current candidate resource IDs.

Compare RAM only with RAM budgets and storage only with storage capacity/free
space. Required accelerator packages must have physical, profile, and current
memory support. Optional accelerator packages remain eligible through explicit
CPU-only degradation. Do not select a device, evict another expert, allocate
context, or claim runtime ABI support in this phase.

## Consequences

- Compatibility results preserve both named validation profiles.
- Current pressure does not permanently label a capable host incompatible.
- Optional acceleration degrades visibly instead of silently disappearing.
- Required GPU-style resources cannot bypass a CPU-only profile.
- Phase 6.5 can consume explicit trust and compatibility evidence.
- Phase 7 remains responsible for live placement, runtime/device support,
  transfer cost, cache, context, and eviction.
- The schema catalog increases to 47 strict roots.

## Alternatives considered

1. Check only physical host totals: rejected because cgroup/profile ceilings and
   OS headroom are authoritative.
2. Check only current free resources: rejected because temporary contention is
   not permanent incompatibility.
3. Treat optional acceleration absence as failure: rejected because CPU fallback
   is explicitly declared.
4. Add SSD bytes to memory capacity: rejected because storage and RAM have
   different semantics and transfer costs.
5. Return a placement plan: rejected because placement and eviction belong to
   the Phase 7 scheduler.

## Evidence

- `src/fam_os/experts/compatibility.py`
- `src/fam_os/experts/compatibility_contracts.py`
- `tests/unit/test_expert_hardware_compatibility.py`
- `schemas/v1alpha1/fam.expert.compatibility-report.schema.json`
