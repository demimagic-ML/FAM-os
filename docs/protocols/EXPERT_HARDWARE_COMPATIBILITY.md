# Expert Hardware Compatibility

## Purpose

Phase 6.4 evaluates whether a validated expert package can fit a physical host
and one selected effective resource profile. It separates permanent
incompatibility from profile policy, current contention, and safe CPU fallback.
It does not install the package or choose a runtime placement.

The report contract is `fam.expert.compatibility/v1alpha1`.

## Inputs

```text
current ExpertManifest
captured HostInventory
composed EffectiveResourceBudget
  -> ExpertCompatibilityEvaluator
  -> ExpertCompatibilityReport
```

The budget must reference the supplied inventory and may mention only its
accelerator and storage IDs. This prevents a compatibility result from mixing
two machine snapshots or profiles.

## Checks

System-memory need is the greater of `estimated_resident_bytes` and
`minimum_system_memory_bytes`.

- CPU architecture is checked against the manifest's optional architecture
  allowlist.
- Required system memory is checked first against physical RAM, then against
  the profile scheduler limit, then against currently available scheduler RAM.
- Package storage bytes are checked against physical storage capacity and
  current free bytes.
- Required accelerator memory is checked against visible accelerator memory,
  profile placement/budget, and current schedulable accelerator memory.

Swap and SSD capacity are never added to RAM. Storage compatibility means the
package bytes can be stored; it does not claim that storage behaves as model
memory. Context allocation, split CPU/GPU placement, cache accounting, transfer
cost, and eviction remain Phase 7 scheduler decisions.

## Statuses

| Status | Meaning |
|---|---|
| `compatible` | Hard requirements and current profile capacity are available now |
| `compatible_cpu_only` | Optional acceleration is unavailable or busy, but CPU execution remains allowed |
| `currently_constrained` | Host/profile can support the expert, but current RAM, VRAM, or free storage is insufficient |
| `incompatible` | CPU architecture, physical capacity, or a hard profile/accelerator requirement cannot be satisfied |

Stable reason codes identify the limiting layer with `hardware.*`, `profile.*`,
`current.*`, or `degradation.*` prefixes. Reports also expose currently viable
storage and accelerator IDs, but these are candidates, not placements.

## Two-profile invariant

Compatibility is profile-specific. A GPU-capable host can legitimately produce
`compatible_cpu_only` or `incompatible` under `compat-cpu-16gb` because that
profile explicitly disables accelerator placement. The same package may be
`compatible` under `full-reference-workstation` when its RAM/VRAM/storage
requirements fit the full effective budget.

This preserves minimum-machine evidence without artificially constraining the
reference workstation.

## Accelerator scope

The current manifest declares accelerator memory and optionality but not a
provider/device-kind ABI. Phase 6.4 therefore treats matching accelerator
memory as a generic candidate. Phase 7 placement must additionally consult the
selected runtime adapter's actual GPU/NPU/offload support before activation; a
compatibility candidate is not proof that one runtime can execute on every
accelerator kind.

## Lifecycle boundary

An accepted package trust report and a compatible hardware report are both
required inputs to Phase 6.5. Neither report alone mutates install state. A
`currently_constrained` package may be installed but must not activate until a
later live scheduler admission succeeds.
