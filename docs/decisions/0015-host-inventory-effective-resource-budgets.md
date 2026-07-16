# ADR 0015: Separate host inventory from effective resource budgets

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The Phase 1 `HardwareProfile` describes read-only host facts, while the original `ResourceBudget` describes only a per-expert RAM, swap, context, and device allowance. Neither can represent CPU topology and allocation, an effective cgroup ceiling, explicit operating-system headroom, per-device VRAM, SSD cache and I/O limits, or current pressure.

The reference workstation must expose its CPU, RAM, RTX VRAM, and NVMe tiers without treating the 16 GiB CPU baseline as a default. At the same time, physical visibility cannot imply permission to use a device or every available byte.

## Decision

FAM_OS defines two additive scheduler-owned contract families:

- `fam.hardware.inventory/v1alpha1` for immutable captured host facts.
- `fam.hardware.budget/v1alpha1` for a timestamped effective scheduling envelope.

Host inventory identifies CPU topology, physical memory and swap, accelerator kind and memory, and storage medium, capacity, availability, and cache eligibility. It does not grant allocation authority.

An effective budget records visible versus schedulable CPU IDs, reserved CPU IDs, scheduler and cgroup quotas, RAM ceilings and headroom, service swap, accelerator placement and VRAM budgets, SSD cache and I/O budgets, and normalized current pressure. Scheduler ceilings plus reserved headroom cannot exceed their effective ceiling. Current usage may exceed a scheduler ceiling so an over-budget state remains observable.

The reserved validation-profile names carry explicit purposes. `compat-cpu-16gb` cannot allow accelerator placement. `full-reference-workstation` represents full-host capability but does not require saturation or hard-code this machine's measured capacities. Concrete profile documents are Phase 2.11 work.

The existing `HardwareProfile` Linux adapter output and per-expert `ResourceBudget` remain unchanged for Phase 1 compatibility. Migration, serialization, and composition happen in later Phase 2 steps.

## Consequences

- Hardware capacity, enforcement, scheduling policy, headroom, and transient pressure are no longer collapsed into one number.
- A physically visible GPU can be explicitly unavailable to the compatibility profile.
- VRAM and SSD cache remain separate resource domains from system RAM.
- The full-workstation profile can expose all hardware tiers while preserving bounded scheduler authority.
- Linux and vendor command shapes remain in adapters rather than these contracts.
- Phase 2.7 must define serialization and cross-version compatibility.
- Phase 2.8 must compose discovery, named profiles, user policy, cgroup state, and session overrides into an effective budget.
- Phase 2.11 must create validated concrete instances for both reserved profiles.

## Alternatives considered

1. Extend the original per-expert `ResourceBudget`: rejected because expert placement and the machine-wide effective envelope are different lifecycles.
2. Treat `HardwareProfile.memory.available_bytes` as allocatable RAM: rejected because cgroups, headroom, pressure, and foreground work can reduce it.
3. Hide GPUs entirely in CPU-only mode: rejected because discovery and placement authority must remain distinguishable.
4. Add SSD free bytes to memory capacity: rejected because storage latency, transfer cost, persistence, and failure modes are different.
5. Reject current usage above the scheduler limit: rejected because limit reductions and pressure events must remain representable for recovery.
6. Bind the contracts directly to cgroup or NVIDIA payloads: rejected because those systems remain replaceable adapters.

## Evidence

- `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md` documents field meanings and invariants.
- `tests/unit/test_host_inventory_schema.py` covers topology, physical tiers, versions, timestamps, and identity uniqueness.
- `tests/unit/test_effective_resource_budget_schema.py` covers cgroup-aware CPU/RAM bounds, headroom, VRAM authority, SSD cache/I/O, pressure, and profile separation.
- ADR 0011 and `docs/architecture/HARDWARE_VALIDATION_PROFILES.md` define the two required validation purposes.
