# ADR 0011: Dual hardware validation profiles

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1 intentionally reproduced the parent RNF experiments in a CPU-only service with a 16 GiB memory ceiling and zero swap. This proved a useful minimum-machine baseline, but the reference development PC has a 24-core Intel Core Ultra 9 285K, approximately 64 GiB RAM, an RTX 5080 with approximately 16 GiB VRAM, and a 2 TB NVMe SSD.

Continuing to force every benchmark through the constrained service would hide GPU placement, larger-context and larger-expert opportunities, CPU/GPU cooperation, SSD-backed model loading, and the quality the actual workstation can provide. Removing the constrained profile entirely would lose minimum-machine evidence.

## Decision

FAM_OS will maintain two named validation profiles:

- `compat-cpu-16gb`: CPU-only, 16 GiB service memory ceiling, zero service swap.
- `full-reference-workstation`: GPU-enabled, all logical CPUs visible, no artificial 16 GiB ceiling, explicit operating-system headroom, and measured use of CPU, RAM, VRAM, and NVMe tiers.

Both profiles run comparable workloads with the same prompts, contexts, verifier definitions, and release policy. Verified quality is compared before performance.

Full capability means every resource tier is available to scheduling and telemetry; it does not require saturating every tier. The full profile still has explicit effective limits and reserves so FAM_OS does not make Linux unusable.

SSD usage is modeled as storage, memory-mapped backing, and cache with transfer cost. It is not added to RAM totals, and uncontrolled operating-system swap is not treated as neural paging.

## Consequences

- The CPU-only Phase 1 results remain valid compatibility evidence rather than the workstation default.
- Phase 2 must version host inventory, effective limits, headroom, and named validation profile schemas.
- Benchmark composition must become profile-driven before the first full-workstation baseline.
- Hardware reports must distinguish host facts, cgroup facts, GPU facts, SSD I/O, and transient availability.
- Scheduler work must preserve quality and explain CPU, GPU, RAM, VRAM, and storage decisions.
- Published claims must name the profile used.

## Alternatives considered

1. Run only the 16 GiB CPU profile: rejected because it artificially discards the reference workstation's strongest capabilities.
2. Run only the full workstation: rejected because minimum-machine compatibility would become untested.
3. Give FAM every byte and CPU without a reserve: rejected because an OS intelligence service must coexist with the user's applications.
4. Count SSD or host swap as extra RAM: rejected because latency, failure behavior, and semantics are materially different.
5. Maintain separate benchmark programs per profile: rejected because duplicated orchestration would invalidate direct comparisons and drift over time.

## Evidence

- Read-only probes on 2026-07-16 recorded the resource snapshot in `docs/architecture/HARDWARE_VALIDATION_PROFILES.md`.
- Phase 1 CPU-only evidence is preserved in `artifacts/parity/phase1-parity-20260716-095056-252893.json`.
- Existing `HardwareProfile` and NVIDIA discovery contracts can represent CPU, RAM, storage, GPU, NPU, and runtime facts without an Ollama dependency.
- Existing cgroup evidence demonstrates why host inventory and effective service limits must remain separate.
