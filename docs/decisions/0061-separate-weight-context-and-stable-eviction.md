# ADR 0061: Separate weight and context accounting with stable safe eviction

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Live memory, context bounds, and durable residency existed, but legacy manifest
resident estimates could not safely be combined with context because their
meaning was not an explicit weight-only contract. Directly evicting whatever a
runtime listed also risked active requests and nondeterministic choices.

## Decision

Create strict replayable admission request and decision roots. Require a
provenance-bearing resident-weight estimate that excludes context and a context
estimate that excludes weights. Charge weights only for cold activation and
charge the request context bound for cold or warm activation.

Fail closed for degraded or non-authoritative memory observations. Consider only
warm, non-requested experts eligible for eviction. Sort by retention priority,
oldest use, then expert identity, and select a minimal stable prefix. Phase 7.4
records policy only; the durable residency coordinator performs later eviction.

## Consequences

- Weight and context bytes cannot silently be double-counted.
- Active and ambiguous evicting experts cannot be policy victims.
- Every result is deterministic and replayable from strict captured inputs.
- Strong experts can be admitted on the full host while remaining honestly
  rejected by the constrained compatibility profile.
- CPU/GPU split and transfer costs remain explicitly deferred to Phase 7.6.
- The strict schema catalog increases from 56 to 58 roots.

## Alternatives considered

1. Reuse `estimated_resident_bytes` unchanged: rejected because it did not prove
   that context was excluded.
2. Evict largest first: rejected because it ignores declared retention value.
3. Evict active experts when necessary: rejected because admission cannot cancel
   an unrelated in-flight request.
4. Include VRAM in the same scalar: rejected because RAM and VRAM are different
   placement tiers and split accounting is Phase 7.6.

## Evidence

- `src/fam_os/scheduler/admission_contracts.py`
- `src/fam_os/scheduler/admission_policy.py`
- `src/fam_os/scheduler/admission_inputs.py`
- `tests/unit/test_deterministic_admission_policy.py`
- `tests/integration/test_reference_admission_replay.py`
- `artifacts/scheduler/phase7.4/reference-admission-replay/`
