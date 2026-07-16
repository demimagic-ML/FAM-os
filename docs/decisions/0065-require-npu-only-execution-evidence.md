# ADR 0065: Require NPU-only execution evidence for NPU micro-experts

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The workstation exposes an Intel Arrow Lake NPU through `intel_vpu`, but physical
discovery does not prove that a userspace model executed there. OpenVINO can
offer `CPU`, `AUTO`, and other device paths, and a permissive probe could pass
while silently using the CPU. The host also lacks a directly installed OpenVINO
runtime and the interactive user lacks direct access to the accelerator group.

## Decision

FAM records physical, runtime, and inference gates separately. A supported NPU
report requires `NPU` in runtime discovery, an explicit `NPU` compile target,
exactly `("NPU",)` in the compiled model's execution devices, and
`fallback_used=false`. Unsupported investigations name one blocking gate and
contain no micro-expert execution evidence.

The reference proof uses a checksum-pinned, network-disabled, read-only
container with only `/dev/accel/accel0` delegated. It does not change host group
membership or install host packages. The proof model is a deterministic linear
router whose purpose is verifying execution and evidence plumbing, not asserting
production model quality.

## Consequences

- CPU emulation and OpenVINO `AUTO` cannot be labeled NPU evidence.
- Runtime and model digests make the live result auditable.
- Direct host access and delegated container access remain distinguishable.
- The scheduler cannot yet admit production NPU workloads; later work must add
  NPU capacity/accounting and benchmark-qualified expert packages.
- Reproduction requires Docker authority, network access while building the
  pinned image, and the physical Intel accelerator device.
