# Live scheduler resource observation

## Purpose

`fam.scheduler.live-resources/v1alpha1` is the repeated, decision-time resource
input for the hardware scheduler. It does not replace host inventory or the
effective budget. Inventory says what exists, the budget says what FAM may use,
and a live observation says what remains available now.

## Sampling boundary

`LiveResourceSampler` reads one FAM-owned cgroup scope plus optional managed
child services. The scope reading is inclusive and authoritative for admission;
child readings exist only for attribution and OOM evidence. Child memory is
never added to scope memory.

The first valid sample records cumulative CPU usage and has `baseline` status.
A later sample linked by observation ID derives interval CPU usage and normalized
utilization from the monotonic cgroup counter. A counter reset or missing source
is explicit degradation, never an invented delta.

## Capacity rules

- Effective CPU and RAM cannot exceed the immutable composed budget or a lower
  live cgroup ceiling.
- Operating-system memory headroom remains inside the effective limit. If an
  external cgroup ceiling is smaller than that reserve, schedulable memory falls
  to zero before the reserve is overstated.
- Scope memory is authoritative. A child-only fallback is useful attribution but
  reports zero admissible memory because unknown scope occupants may exist.
- An allowed accelerator without telemetry degrades and has unknown (`null`)
  current/free memory. It is never represented as empty VRAM.
- A policy-disabled zero-budget accelerator may remain unobserved without
  degrading admission because placement is already impossible.
- Missing scheduler-cache telemetry degrades and exposes unknown (`null`) free
  cache, not the full storage budget.
- Storage is measured as regular-file bytes under configured absolute cache
  roots. Traversal is entry-bounded and never follows symbolic links.

## Status

- `baseline`: first complete-source sample; cumulative CPU has no prior delta.
- `complete`: linked later sample with a valid CPU delta and no reason codes.
- `degraded`: one or more stable reason codes; it may be the first or a later
  sample and may still retain measurements that are trustworthy.

## Linux adapters

`CgroupV2ResourceObserver` supplies scope/child CPU, RAM, swap, limits, and OOM
events. `NvidiaAcceleratorRuntimeObserver` maps privacy-safe `nvidia-smi`
readings to stable `gpu-N` inventory IDs. `DirectoryStorageRuntimeObserver`
accounts only FAM-configured cache roots. Intel NPU telemetry remains Phase 7.8;
current profiles assign the discovered NPU zero placement budget.

## Canonical evidence

`artifacts/scheduler/phase7.1/` contains fresh privacy-reviewed captures and two
linked observations for both named profiles. Canonical summaries are under
`compat-observations-canonical/` and `full-observations-canonical/`. Both move
from baseline to complete, contain nonzero CPU deltas, use authoritative scope
memory, and end with the transient service inactive. The compatibility profile
keeps GPU placement disabled; the full profile enables the RTX GPU.

The earlier sibling observation directories are retained failed diagnostics:
they classified a missing, policy-disabled zero-budget NPU as degradation. They
must not be substituted for the canonical captures or deleted from history.
