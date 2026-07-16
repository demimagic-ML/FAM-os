# Hardware Validation Profile Documents

## Contract family

Concrete benchmark profiles use `fam.validation-profile/v1alpha1`. The public `ValidationProfileDocument` composes:

- stable identity, display name, and purpose description;
- CPU-compatibility or full-host workload mode;
- one existing `ValidationProfileConfiguration` scheduler policy;
- one provider-neutral `ServiceResourceEnvelope`;
- exact alpha contract version.

The strict serialized root is `fam.configuration.validation-profile-document/v1alpha1`. The checked documents live in `configs/profiles/` and are validated by the same decoder and generated Draft 2020-12 schema as other public contracts.

## Why the service envelope is separate

Scheduler policy answers how much of an admitted service envelope FAM may schedule. The service envelope answers what the supervisor/service composition may expose and enforce. The distinction is required for the CPU baseline:

```text
16 GiB service memory ceiling
  - 2 GiB explicit service/OS headroom
  = 14 GiB scheduler memory ceiling
```

Collapsing those numbers would either erase headroom or falsely call 14 GiB the service cgroup limit. The service envelope also declares swap, optional CPU quota, and whether accelerators are denied or discovered; it contains no systemd property or provider environment variable.

## `compat-cpu-16gb`

`configs/profiles/compat-cpu-16gb.json` is the minimum-machine regression policy:

- workload mode: `cpu_compatibility`;
- service memory maximum: 17,179,869,184 bytes (16 GiB);
- scheduler RAM maximum: 15,032,385,536 bytes (14 GiB);
- explicit headroom: 2,147,483,648 bytes (2 GiB);
- service and scheduler swap: zero;
- accelerator visibility: `deny_all`;
- accelerator placement and schedulable VRAM: disabled/zero;
- one logical CPU reserved when the host has enough CPUs;
- cache-eligible storage may be used under a 25 percent ratio, 100 GiB maximum, and 20 GiB free-space reserve.

The contract requires the exact 16 GiB service ceiling, zero swap, CPU workload mode, denied accelerator visibility, disabled accelerator placement, and scheduler RAM plus headroom no greater than the service ceiling.

A GPU may remain present in `HostInventory`; composition emits it with placement false and zero schedulable memory. This preserves the difference between physical discovery and profile authority.

## `full-reference-workstation`

`configs/profiles/full-reference-workstation.json` is quality-first policy for the reference development class:

- workload mode: `full_host`;
- no profile-level service RAM or CPU quota;
- all limits remain subordinate to recaptured host/cgroup enforcement;
- 2 logical CPUs reserved for Linux and foreground work;
- 12 GiB explicit RAM headroom;
- service and scheduler swap: zero;
- discovered accelerators visible and schedulable;
- 87.5 percent VRAM scheduling ratio with a 1 GiB reserve per discovered accelerator;
- cache-eligible storage uses a 50 percent ratio, 500 GiB maximum, and 100 GiB free-space reserve.

The contract rejects a full profile that uses a 16 GiB-or-smaller service ceiling, disables accelerator scheduling, hides discovered accelerators, or selects CPU-compatibility workload mode.

## Reusable policy versus captured facts

Neither checked profile contains a GPU ID, CPU model, mount path, home directory, model name, provider name, RAM total, current availability, or driver/runtime version. Those values change and may reveal machine information. They belong to a separately captured, privacy-reviewed `DiscoveredResourceState` for each measured run.

Tests compose the two policy documents against the same deterministic discovered workstation fixture. The minimum profile is given its declared 16 GiB enforcement ceiling; the full profile retains the fixture's recaptured capacity. This proves policy behavior without presenting the fixture as a current live measurement.

## Boundaries

- The documents are desired policy, not proof that cgroups, GPU visibility, or I/O controls were enforced.
- Phase 2.12 translates the service envelope through one profile-driven benchmark composition path documented in `docs/operations/PROFILED_BENCHMARKS.md` and ADR 0021.
- Phase 2.13 must capture the live reference workstation state separately and produce raw smoke evidence.
- Published benchmark results must identify the profile document and captured discovery artifact used.
- Changes to either profile's public meaning require a new profile document/version and compatibility evidence; do not rewrite `v1alpha1` semantics silently.
