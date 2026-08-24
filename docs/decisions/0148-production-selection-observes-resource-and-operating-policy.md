# ADR 0148: Production selection observes resource and operating policy

Status: Accepted

## Context

FAM_OS already had cgroup-aware scheduler contracts, validation-profile
reserves, NVIDIA observations, and deterministic battery, thermal, foreground,
and idle policy. The installed product did not compose them. Its local selector
called a shortcut that added `/proc/meminfo` `MemAvailable` to free VRAM and
subtracted a fixed 2 GiB. Predictive prewarming repeated the same shortcut.

That path could select or prewarm an escalation expert while the host was hot,
busy, or on low battery. Managed Ollama's enforced memory ceiling was also
invisible to selection. Phase evidence proved isolated policy components but
did not prove their production reachability.

## Decision

The product composes one `ProductCapacityObserver` and gives the same live
projection to request selection and predictive prewarming. The projection
contains raw available host and accelerator bytes, explicit host/VRAM reserves,
an optional managed-cgroup allocation ceiling, the maximum permitted expert
tier, background and speculation permissions, and reason codes.

Linux operating-state observation is bounded and shell-free. It reads system
batteries, valid sysfs and NVIDIA temperatures, normalized load, and desktop
idle time. Missing authoritative thermal data disables speculation. An
unreadable system battery disables speculative background work. Tier policy
always overrides residency and escalation preference.

The full-workstation projection uses the existing 12 GiB host and 1 GiB VRAM
profile reserves. The compatibility projection uses the existing 2 GiB host
reserve. For managed Ollama, cold host allocation is additionally clamped by
the observed cgroup remainder and fails closed when the managed snapshot is
missing. External Ollama is explicitly labelled unmanaged and is not assigned
a fictional cgroup ceiling.

Predictive prewarming requires both speculative-prefetch and idle-background
permission. It remains non-evicting.

## Consequences

- Production request selection cannot bypass a battery or thermal tier cap by
  preferring an already resident or stronger model.
- Background adaptation cannot load a model merely because bytes appear free.
- The selected model and prewarm receipt carry the observations that affected
  the decision.
- A thermal micro cap safely yields no fitting generation model until a
  production micro expert exists; it does not silently use a larger tier.
- Managed resource uncertainty prevents new cold allocation while an external
  runtime remains an explicit lower-assurance mode.
- This decision does not claim production eviction or durable residency
  coordination. Those require active inference leases and confirmed unloads.

## Alternatives considered

- Keeping operating policy as offline evidence was rejected because isolated
  correctness does not protect the installed path.
- Encoding the restrictions in prompts was rejected because resource authority
  is deterministic policy, not model advice.
- Treating unknown managed cgroup capacity as unlimited was rejected because it
  can violate the enforced service ceiling.
- Automatically unloading every other Ollama model was rejected because the
  product does not yet hold cross-request active leases and must not evict
  external or in-flight workloads.

## Evidence

- `src/fam_os/adapters/linux/operating_state.py`
- `src/fam_os/product/composition/live_capacity.py`
- `src/fam_os/core/production/model_selection.py`
- `src/fam_os/product/live_model_prewarm.py`
- `src/fam_os/product/composition/runtime_unit.py`
- `tests/unit/test_linux_operating_state.py`
- `tests/unit/test_product_live_capacity.py`
- `tests/unit/test_production_model_policy.py`
- `tests/unit/test_product_live_adaptation.py`
