# ADR 0060: Persist residency before provider mutation and reconcile ambiguity

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Loaded-model inspection and confirmed unload existed, but the scheduler had no
durable distinction between installed, loaded-idle, request-active, and unloading
experts. Process crashes could lose request ownership or eviction intent. Treating
an unload call or missing state file as cold would overstate resource release.

## Decision

Publish a strict revisioned residency catalog with exactly cold, warm, active,
and evicting states. Bind records to expert and runtime artifact IDs. Make active
state structurally equivalent to one or more expiring request leases and evicting
state structurally equivalent to one exact eviction ID with no leases.

Persist evicting through compare-and-swap before calling the runtime. Persist
cold only after provider-confirmed absence. On ambiguous unload errors, observe
again: present restores warm, absent completes cold, and unavailable observation
leaves evicting for startup reconciliation.

Use provider reconciliation as a crash-recovery boundary. Warm/evicting absence
can become cold; active absence is an explicit conflict. Persist state through a
private locked atomic JSON adapter with exact schema decoding and revisions.

## Consequences

- New requests cannot race onto an expert selected for eviction.
- Crashed request leases can expire instead of pinning memory indefinitely.
- A failed provider call cannot silently claim memory was freed or retained.
- Installed/disabled package state remains separate from runtime residency.
- Later admission and eviction policy can operate on revisioned facts rather than
  direct `/api/ps` snapshots.
- The strict schema catalog increases from 55 to 56 roots.

## Alternatives considered

1. Infer all state from `/api/ps`: rejected because it has no request leases or
   durable eviction intent.
2. Keep state in memory: rejected because process restart loses safety barriers.
3. Set cold immediately after unload request: rejected because acknowledgement is
   not confirmed allocator/model absence.
4. Restore warm on every unload exception: rejected because a late response may
   arrive after successful absence.
5. Move residency into package lifecycle state: rejected because installation and
   runtime memory have independent ownership and failure modes.

## Evidence

- `src/fam_os/scheduler/residency_contracts.py`
- `src/fam_os/scheduler/residency_service.py`
- `src/fam_os/scheduler/residency_repository.py`
- `src/fam_os/adapters/filesystem/residency_state.py`
- `tests/unit/test_expert_residency_service.py`
- `tests/unit/test_residency_state_repository.py`
- `tests/integration/test_residency_lifecycle_evidence.py`
- `artifacts/scheduler/phase7.3/qwen-residency-lifecycle-canonical/`
