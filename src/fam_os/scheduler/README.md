# Scheduler ownership

Owns context, memory, device, placement, residency, eviction, and escalation budgets.

It chooses policy from measured resources but performs no privileged operation itself. The supervisor enforces approved limits through adapters.

The scheduler also owns the provider-neutral `HardwareProfile` and `HardwareDiscovery` port. A host profile is inventory, not an execution budget; effective cgroup limits and live pressure must be applied separately.

Phase 2 adds richer `fam.hardware.inventory/v1alpha1` and `fam.hardware.budget/v1alpha1` contract families under `scheduler/resources/`. They separately represent CPU topology, physical RAM, accelerator VRAM, storage tiers, effective/cgroup limits, scheduler ceilings, explicit headroom, and current pressure. See `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md` and ADR 0015.

`scheduler/configuration/` owns `fam.configuration/v1alpha1` defaults, trusted profiles, user/session restrictions, discovered enforcement state, pure composition, and ordered decisions. Trusted profiles can replace fallback values; user/session layers can only restrict; discovery always clamps the result. The Phase 1 `HardwareProfile` and per-expert `ResourceBudget` remain compatibility contracts until later runtime migration. See `docs/protocols/CONFIGURATION_LAYERING.md` and ADR 0019.

`PlacementPlanner` chooses a typed `PlacementPlan`, including context budget and expert IDs to evict. Core may execute that plan by resolving expert IDs and unloading their runtime models, but Core must not invent an eviction decision. Phase 1.9 consumes the context allocation; enforcement of the plan's complete memory, swap, and device budget remains scheduler/supervisor work.

`LiveResourceSampler` owns the repeated decision-time view layered beneath later
placement. It treats the FAM scope cgroup as inclusive, keeps child readings for
attribution, derives CPU load from linked cumulative samples, and never turns
missing GPU/cache telemetry into free capacity. See
`docs/protocols/LIVE_SCHEDULER_RESOURCE_OBSERVATION.md` and ADR 0058.

`ContextMemoryEstimator` separates model weights from request-owned memory. It
uses grouped-query KV bounds for autoregressive experts and a quadratic attention
bound for encoders, retains output/concurrency growth and every conservative
assumption, and rejects package context overflow. See
`docs/protocols/CONTEXT_MEMORY_ESTIMATION.md` and ADR 0059.

The durable residency catalog separates cold, warm, active, and evicting runtime
artifacts. Request leases and eviction identities are revision-bound; provider
reconciliation resolves crash ambiguity, and cold requires confirmed absence.
See `docs/protocols/EXPERT_RESIDENCY_LIFECYCLE.md` and ADR 0060.

`DeterministicAdmissionPolicy` binds an authoritative live memory observation,
a residency revision, context-only request bytes, and provenance-bearing
weight-only bytes. It fails closed on unknown scope, never selects active or
evicting experts, and uses stable priority/age/identity eviction order. It emits
policy documents only; the residency coordinator owns mutation. See
`docs/protocols/DETERMINISTIC_ADMISSION_AND_EVICTION.md` and ADR 0061.

The Phase 7.5 compatibility baseline applies the 16 GiB limit to an isolated
service rather than falsifying a stronger host's capacity. Its strict report
proves simultaneous Llama/Qwen CPU residency, zero VRAM/swap/OOM, a 2 GiB
reserve, stable strong-model rejection, durable unload, and inactive cleanup.
See `docs/protocols/CPU_ONLY_16GIB_BASELINE.md` and ADR 0062.

Phase 7.6 uses independent host-RAM and per-device-VRAM vectors, explicit
provider-neutral layer placement, conservative host safety reservation, and
observed Ollama/NVIDIA allocation. Transfer cost uses provider VRAM bytes over
disclosed model-load duration. The full-profile proof includes real Laguna and
Gemma CPU/GPU splits. See `docs/protocols/GPU_SPLIT_PLACEMENT.md` and ADR 0063.

Phase 7.7 keeps durable SSD bytes, `mincore` page residency, cgroup/process
memory, and physical/logical I/O distinct. It uses a temporary verified model
store for safe cold-cache evidence, cumulative load-I/O budgets, and optional
fail-closed systemd/cgroup bandwidth enforcement. See
`docs/protocols/SSD_MODEL_PAGING.md` and ADR 0064.
