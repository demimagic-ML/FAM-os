# ADR 0020: Separate reusable dual-profile policy from captured machine state

**Status:** Accepted  
**Date:** 2026-07-16

## Context

ADR 0011 requires both a 16 GiB CPU-only baseline and a full-reference-workstation mode. Phase 2.8 can compose scheduler policy, but a scheduler limit alone cannot express the service's cgroup memory ceiling, swap ceiling, or accelerator visibility. Embedding those controls in benchmark Python would make the profile implicit and provider-specific.

The reference workstation facts also change and may contain privacy-sensitive identifiers. Reusable policy must not freeze a GPU bus ID, mount path, username, current free space, driver version, or provider model into the profile.

## Decision

FAM_OS adds the `fam.validation-profile/v1alpha1` `ValidationProfileDocument`. It composes one scheduler `ValidationProfileConfiguration` with a provider-neutral `ServiceResourceEnvelope` and workload mode. The strict serialized root is registered with the existing schema catalog.

Two checked documents are canonical:

- `compat-cpu-16gb.json`: 16 GiB service memory ceiling, 14 GiB scheduler ceiling, 2 GiB headroom, zero swap, CPU compatibility mode, and denied accelerator visibility/placement.
- `full-reference-workstation.json`: no artificial profile CPU/RAM ceiling, 2 reserved logical CPUs, 12 GiB RAM headroom, zero swap, discovered accelerator visibility, 87.5 percent VRAM scheduling with a 1 GiB reserve, and bounded NVMe cache policy.

The profile document contains desired reusable policy only. Live inventory, cgroup limits, current RAM/VRAM/cache use, pressure, paths, device IDs, and software versions remain in a separately captured `DiscoveredResourceState`.

The CPU profile's service ceiling and scheduler ceiling are distinct so headroom remains explicit. The full profile's absent service RAM maximum means no profile-level artificial ceiling; discovery and enforcement still clamp the result.

## Consequences

- Both required modes are exact-schema data rather than hidden branches in orchestration code.
- The compatibility baseline can be reproduced on stronger hardware without pretending the GPU is physically absent.
- The full profile can use host CPU, RAM, VRAM, and cache-eligible NVMe without inheriting the 16 GiB ceiling.
- Profile policy can be reviewed without publishing a live machine snapshot.
- Phase 2.12 can build one service composition path over the service envelope.
- Phase 2.13 must pair the full profile with a fresh privacy-reviewed discovery artifact and measurements.
- Changing the public profile meaning requires explicit version and evidence updates.

## Alternatives considered

1. Store only scheduler policy: rejected because it cannot express the service cgroup ceiling or accelerator visibility.
2. Put systemd properties and environment variables in the profile: rejected because service managers and inference providers remain adapters.
3. Put the live workstation inventory in the profile: rejected because reusable policy and time-varying/private facts have different lifecycles.
4. Hard-code two branches in benchmark Python: rejected because composition would drift and schemas could not validate the modes.
5. Give the compatibility scheduler all 16 GiB with no headroom: rejected because the service and Linux/foreground reserve must remain explicit.
6. Give the full profile unlimited unreserved resources: rejected because full capability does not mean making the desktop unusable.

## Evidence

- `configs/profiles/compat-cpu-16gb.json`
- `configs/profiles/full-reference-workstation.json`
- `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md`
- `src/fam_os/scheduler/configuration/profiles.py`
- `tests/contract/test_validation_profiles.py`
- Generated `schemas/v1alpha1/fam.configuration.validation-profile-document.schema.json`
- ADR 0011, ADR 0015, ADR 0018, and ADR 0019
