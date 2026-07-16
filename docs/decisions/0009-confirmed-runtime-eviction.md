# ADR 0009: Confirmed runtime eviction is an activation barrier

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 1.10 repeated the three CPU-only residency policies through FAM_OS. In the first migrated comparison, Ollama acknowledged the Granite `keep_alive=0` request, but the immediately following loaded-model observation still contained Granite. The 14B expert began loading before eviction completed, and the nominal eviction policy peaked at 13,167,058,944 bytes versus 12,375,568,384 bytes for the persistent policy. That diagnostic report correctly failed the expected memory relation.

A separate repeat later observed the expected reduction, showing that fire-and-forget unload behavior creates a race rather than a deterministic scheduling transition. Scheduler policy cannot treat an acknowledged runtime request as proof that capacity is available.

## Decision

`InferenceRuntime.unload(model_ref)` means confirmed logical absence: it returns only after `loaded_models()` no longer contains that model, or it raises a runtime error within a bounded timeout.

The Ollama adapter sends the existing `keep_alive=0` request and then polls `/api/ps`. Poll interval and timeout are adapter settings. Core and scheduler policy remain unaware of Ollama endpoints and timing behavior.

Confirmed absence is an activation barrier, not a complete memory-reclamation claim. A runtime may retain allocator memory or the operating system may retain charged file cache after a model disappears from its logical loaded-model list. Placement policy must continue to use cgroup current, peak, pressure, and event telemetry when deciding whether enough capacity exists.

## Consequences

- Scheduler-selected eviction becomes deterministic at the runtime contract boundary.
- An escalation cannot start merely because the runtime acknowledged an unload request.
- Slow or stuck eviction fails explicitly instead of silently overlapping model residency.
- Ollama unload now performs one or more loaded-model queries and may add bounded latency.
- Runtime adapters must implement confirmed absence or report failure.
- Cgroup resource observation remains authoritative for actual capacity; `/api/ps` is not a memory ledger.

## Alternatives considered

1. Keep fire-and-forget unload and add a sleep in benchmark tools: rejected because timing guesses do not establish state and production scheduling would retain the race.
2. Poll in `PlacementExecutor`: rejected because completion semantics and provider errors belong to the runtime adapter.
3. Treat the first failed comparison as ordinary noise: rejected because `/api/ps` directly showed the supposedly evicted model still resident.
4. Claim confirmed unload means all memory is reclaimed: rejected because allocator and cgroup memory can outlive logical model residency.

## Evidence

- Diagnostic report `artifacts/parity/policy-parity-20260716-093229-742050.json` preserves the failed pre-barrier comparison.
- Unit tests cover immediate, delayed, and unconfirmed unload behavior.
- The final confirmed-eviction report `artifacts/parity/policy-parity-20260716-094449-098883.json` passed all gates: persistent 14B peaked at 13,093,113,856 bytes, confirmed-eviction 14B at 12,131,512,320 bytes, and persistent 7B at 6,698,876,928 bytes, with no swap or OOM kills.
- The final verified escalation also confirmed economical and router eviction before 14B activation.
