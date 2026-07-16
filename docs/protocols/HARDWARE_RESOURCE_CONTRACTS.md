# Hardware Inventory and Effective Resource Contracts

## Contract families

Phase 2.2 defines two provider-neutral Python contract families:

- `fam.hardware.inventory/v1alpha1` describes physical and discoverable host facts.
- `fam.hardware.budget/v1alpha1` describes the resources FAM may schedule at one point in time.

These markers version the owning domain contracts. Strict JSON encoding, generated schemas, and exact alpha compatibility are implemented by `SERIALIZED_SCHEMA_COMPATIBILITY.md`; configuration composition remains Phase 2.8 work.

## Inventory is not permission

`HostInventory` records an opaque inventory ID, capture time, OS identity, CPU topology, physical memory and swap, accelerators and their memory, and storage tiers. Accelerator and storage IDs are stable references within the captured inventory. Storage explicitly records its medium and whether it may back FAM caches.

Inventory facts never authorize allocation. A visible GPU may have no placement budget, available host RAM may sit outside a service cgroup, and free SSD capacity is not memory.

The Phase 1 `HardwareProfile` remains the read-only Linux adapter's compatibility output. `HostInventory` is the richer Phase 2 schema. Adapter migration and serialized compatibility are deliberately deferred so this contract change does not alter measured scheduling behavior.

## Effective budget

`EffectiveResourceBudget` links to one inventory and one named validation profile. It contains a timestamped snapshot of:

- visible, schedulable, and OS-reserved logical CPUs;
- scheduler and cgroup CPU quotas;
- effective RAM ceiling, scheduler RAM ceiling, explicit headroom, current use, cgroup ceiling, and service swap;
- per-accelerator placement authority, effective VRAM, schedulable VRAM, reserved VRAM, and current VRAM;
- per-storage cache capacity, scheduler cache ceiling, reserved free space, current cache, and optional read/write rate ceilings;
- normalized utilization and stall-pressure readings for CPU, memory, accelerator, and storage resource IDs.

The effective limit is the hard capacity visible after host and enforcement constraints are considered. The scheduler limit is the smaller allocation policy after headroom is withheld. For bounded memory, VRAM, and cache:

```text
scheduler limit + reserved headroom <= effective limit
```

Current usage may exceed a newly reduced scheduler limit. The schema preserves that unsafe observation and reports zero bytes available for new RAM allocations instead of rejecting or hiding the over-budget state.

## Validation-profile identity

The two reserved identities carry different purposes:

| Profile ID | Purpose | Accelerator rule |
|---|---|---|
| `compat-cpu-16gb` | `minimum_compatibility` | Cannot allow accelerator placement |
| `full-reference-workstation` | `full_host_capability` | May budget CPU, RAM, GPU VRAM, and NVMe tiers |

Custom profile IDs use the `custom` purpose. Concrete capacities, headroom amounts, and service composition remain Phase 2.11 and Phase 2.12 configuration, not hard-coded scheduler behavior.

Phase 2.8 deterministically composes desired policy with inventory, enforcement, user restrictions, and session restrictions. See `CONFIGURATION_LAYERING.md` and ADR 0019.

The compatibility contract may record a GPU that is physically visible, but its accelerator budget must set placement authority to false and schedulable VRAM to zero. This makes the difference between discovery and use explicit.

## Invariants

- Contract versions must match exactly.
- Capture and pressure timestamps are timezone-aware.
- CPU, accelerator, storage, and pressure resource IDs are unique.
- CPU allocations are disjoint subsets of the visible CPU set.
- Scheduler CPU quota cannot exceed the schedulable CPU count or a known cgroup quota.
- RAM, VRAM, swap, cache, and I/O quantities cannot be negative.
- Pressure values are normalized to the inclusive range from zero to one.
- Pressure may reference only CPU, memory, or a budgeted accelerator/storage ID.
- SSD cache capacity is never combined with RAM or VRAM capacity.

## Ownership

The scheduler owns these contracts and future composition policy. Linux, cgroup, NVIDIA, and storage probes remain replaceable adapters. The supervisor will enforce approved limits, while telemetry will record measurements without choosing policy.
