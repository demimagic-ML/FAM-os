# Hardware Validation Profiles

## Decision summary

FAM_OS has two required hardware validation profiles with different purposes:

1. `compat-cpu-16gb` proves that the minimum supported Linux PC remains usable without a discrete GPU.
2. `full-reference-workstation` proves that a stronger PC is not artificially reduced to the compatibility ceiling and can use CPU, RAM, GPU VRAM, and SSD capacity as scheduled resource tiers.

These are separate benchmark modes. A result from one must never be labeled as a result from the other.

## Reference workstation snapshot

Read-only probes on 2026-07-16 reported:

| Resource | Observed capability |
|---|---|
| CPU | Intel Core Ultra 9 285K, 24 logical CPUs, 24 cores, one socket |
| System memory | 67,017,834,496 bytes total, 41,909,792,768 bytes available at capture |
| GPU | NVIDIA GeForce RTX 5080, 16,303 MiB VRAM, driver 595.71.05 |
| Primary storage | KIOXIA KXG8AZNV2T04 NVMe, 2,048,408,248,320 bytes raw capacity |
| Root filesystem | ext4, approximately 1.8 TiB, approximately 513.5 GiB available at capture |
| Local inference runtime | Ollama 0.30.11 |

Availability, thermals, loaded models, filesystem space, and software versions are snapshot facts and must be recaptured for each published benchmark. Host swap was already in use by unrelated processes, so every FAM service must report its own cgroup swap rather than infer it from host totals.

## Profile A: `compat-cpu-16gb`

Purpose: minimum-machine compatibility and regression evidence.

- CPU inference only.
- 16 GiB service memory ceiling.
- Zero service swap.
- No GPU or Vulkan visibility.
- SSD available for model files and normal filesystem cache.
- Same prompts, contexts, verifier definitions, and release policy as the compared full-workstation run.

This profile remains required. It is not the default execution profile for the reference workstation.

## Profile B: `full-reference-workstation`

Purpose: quality-first development and measurement on the actual test PC.

- The RTX 5080 is visible to the inference runtime; CPU-forcing environment variables are absent.
- All 24 logical CPUs are visible to the service and scheduler.
- The artificial 16 GiB service ceiling is removed.
- RAM admission uses effective cgroup capacity, current pressure, and an explicit operating-system/user-workload reserve.
- GPU placement records VRAM used, layers or tensors placed, host-to-device transfers where exposed, and fallback/offload behavior.
- NVMe storage participates as model storage, memory-mapped weight backing, cache, artifact storage, and measured load/eviction I/O.
- SSD capacity is never reported as RAM, and uncontrolled host swap is not used as a neural-paging design.
- The benchmark records the exact reserve and effective limits instead of treating the service as unbounded.

"Use the full machine" means every resource tier is discoverable, schedulable, and measured. It does not mean every task must saturate all CPUs, allocate all RAM, or fill VRAM. The scheduler should choose the combination that gives the strongest verified result within latency, responsiveness, thermal, and safety policy.

## Quality and comparison rules

Full-workstation optimization must not lower verified quality merely to report smaller memory or faster first-token latency.

For comparable workloads:

1. Hold task inputs, context limits, verifier definitions, and result policy constant.
2. Record verified pass rate before performance comparisons.
3. Compare model/expert selection, wall and load time, token throughput, CPU utilization, RAM current/peak, VRAM current/peak, bytes transferred, SSD reads/writes, cgroup pressure, swap, and OOM events.
4. Preserve failed and degraded runs as raw artifacts.
5. Report foreground responsiveness and the explicit OS reserve.
6. Explain whether a larger model, longer context, more resident experts, or faster verification produced the quality difference.

The compatibility profile answers, "Can FAM_OS work safely on the minimum PC?" The full profile answers, "What is the best verified intelligence this workstation can sustain while remaining a usable PC?"

## Implementation sequence

1. Phase 2.2 defines versioned host-inventory, effective-limit, headroom, and resource-budget schemas.
2. Phase 2.11 creates both named profiles as validated configuration.
3. Phase 2.12 replaces the CPU-specific benchmark composition with one profile-driven composition.
4. Phase 2.13 captures a privacy-reviewed machine artifact and runs the first GPU-enabled full-workstation smoke baseline.
5. Phase 7 develops production placement, split-offload, transfer, cache, and eviction policy using both profiles as regression gates.

No hardware-specific model name, device index, or path belongs in Core orchestration. Stable profile ceilings and reserves belong in checked configuration data; captured capacity and availability remain separate discovery evidence.

Phase 2.2 is implemented by the contracts documented in `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md` and ADR 0015. Phase 2.11's concrete strict-schema documents are implemented under `configs/profiles/` and documented in `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md` and ADR 0020. Profile-driven service composition and the live privacy-reviewed full-workstation run remain Phase 2.12 and 2.13.
