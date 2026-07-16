# ADR 0022: Privacy-reviewed full-workstation evidence and honest measurement scope

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 2 requires a real full-capability workstation baseline distinct from the 16 GiB CPU compatibility run. Reusing the legacy hardware profile directly would publish hostname, paths, PCI identity, and provider details. Existing cgroup telemetry also lacked CPU and storage I/O, while the delegated user cgroup on this host does not expose `io.stat`.

## Decision

Live Linux discovery maps read-only probes into strict Phase 2 inventory and state documents using opaque `gpu-N`, `npu-N`, and `storage-root` identifiers. It retains capability facts needed by scheduling and excludes hostname, user identity, local paths, storage serials, GPU UUID/PCI address, and raw accelerator device paths. Full-smoke reports retain input filenames only.

The existing cgroup observer now records CPU and I/O counters when controllers expose them. NVIDIA VRAM sampling uses a bounded field query without persistent device identity. Fresh-service loaded-model deltas are recorded as residency-transfer evidence.

When service `io.stat` is unavailable, Linux root-partition counters may provide fallback SSD evidence only when labeled with host scope and window attribution. They must never be presented as service-exclusive bytes.

A smoke report records verification outcome without redefining it. A failed candidate remains withheld and the baseline may be a failed quality gate while still satisfying the Phase 2 requirement to capture raw full-capability evidence.

## Consequences

- Captures can be shared without workstation user/location identifiers.
- Scheduler inputs are strict documents rather than ad hoc command output.
- CPU, RAM, VRAM, model residency, SSD I/O, latency, and failures have explicit provenance.
- Host-partition I/O includes unrelated activity and is unsuitable for per-service accounting.
- The canonical Phase 2.13 quality result is false; it is evidence for later Expert Fabric fitness work, not a reason to release unverified output.
- Earlier diagnostic smoke files created before source-path scrubbing are local-only and noncanonical.

## Alternatives considered

1. Store the legacy profile unchanged: rejected because it contains unnecessary private identity.
2. Record missing cgroup I/O as zero: rejected because unavailable is not zero.
3. Attribute whole-partition I/O to FAM: rejected because concurrent host activity cannot be separated.
4. Relax or replace the verifier until a model passes: rejected because that would invalidate the quality claim.
5. Omit failed runs: rejected because failure behavior and safe withholding are required evidence.

## Evidence

- `src/fam_os/adapters/linux/resource_discovery.py`
- `src/fam_os/adapters/linux/block_io.py`
- `tools/workstation/capture.py`
- `tools/workstation/evidence.py`
- `tools/run_workstation_smoke.py`
- `artifacts/workstation/20260716T113113568743Z/`
- `tests/unit/test_linux_resource_discovery.py`
- `tests/unit/test_linux_block_io.py`
- `tests/unit/test_workstation_evidence.py`
