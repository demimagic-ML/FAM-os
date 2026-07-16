# ADR 0066: Separate cache tiers and replay scheduler policy offline

**Status:** Accepted  
**Date:** 2026-07-16

## Context

FAM observes filesystem page cache, provider weight residency, GPU weight
residency, and NPU compilation state. Treating these as interchangeable cache
bytes would allow SSD-backed pages or one accelerator's allocations to satisfy
pressure in another capacity domain. Scheduler changes also need regression
proof against historical inputs without depending on whatever happens to be
loaded on the current machine.

## Decision

Cache telemetry uses four explicit tiers and tier-local pressure. Cold, warm,
and active states have strict byte/eviction invariants. The deterministic cache
policy considers only warm, evictable, unprotected entries in the requested
tier and emits an ordered recommendation rather than causing side effects.

Policy replay serializes immutable inputs, recorded outputs, and newly replayed
outputs canonically, binds them by SHA-256, and requires byte equality. Replay
invokes the real host-admission, GPU-placement, and cache-retention policies and
must record `current_host_state_consulted=false`.

## Consequences

- Storage, host RAM, VRAM, and NPU state cannot be blended into fake capacity.
- Historical decisions are executable regression fixtures, not prose claims.
- An observation can honestly declare incomplete host coverage.
- A matched replay proves determinism for the exact input, not observation
  completeness or future correctness.
- Phase 7.10 can use cache history, but prefetch remains subordinate to resource
  admission and operating-system reserves.
