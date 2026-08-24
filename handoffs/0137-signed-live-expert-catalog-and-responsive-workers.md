# Handoff 0137: Signed live expert catalog and responsive workers

**Date:** 2026-07-17  
**Plan steps:** Phase 18.3–18.5, 18.7–18.8  
**Status:** Complete  
**Previous handoff:** `0136-installed-unified-core-gateway.md`

## Scope completed

- Persisted the signed release manifest and Ed25519 trust key at installation.
- Re-verified the activated release signature and every component digest during
  production catalog composition.
- Read expert manifests, runtime bindings, and model policy from the signed
  archive; exact coordinate joins expose seven configured local models.
- Added the Qwen3 1.7B economical language package and exact Ollama binding.
- Persisted seven enabled expert records while preserving explicit disables
  across release synchronization.
- Connected selection to live RAM, free VRAM, and Ollama loaded-model state.
- Added a bounded economical, repair, Laguna, and independent Gemma 26B fallback
  chain under a durable global budget.
- Added structured `unverified`, `grounded`, and `verified` assurance to Core
  and Shell results.
- Moved inference to background task workers and fixed SQLite fetch locking so
  cold model loads do not block or terminate the Shell service.
- Split the former 544-line gateway into focused modules; the largest production
  Core module is now 219 lines.

## Installed evidence

The signed `phase18-integrated2` release started from a fresh state, re-verified
its catalog, persisted seven enabled experts, returned an immediate running
snapshot, and completed `INTEGRATED_READY` with structured verified assurance
and independent evidence. Managed Ollama stopped with the service. The earlier
cold 7B specialist load remained Shell-responsive with poll latency at or below
0.007 seconds. Evidence is in
`artifacts/product/phase18/unified-installed-core.json`.

## Validation

- 887 tests pass; seven declared environment skips.
- 184 schemas validate and round-trip.
- Ruff and mypy pass for the production Core, product composition, and storage.
- Unit evidence exercises repair, Laguna-first escalation, Gemma fallback, and
  all three durable budget reservations without weakening exact acceptance.

## Remaining Phase 18 gap

Step 18.6 remains open. The installed exact-output verifier is real, but Python,
retrieval, math, media, and application postcondition verifiers must be selected
from declared bindings through the same production gateway. The application
portion depends on Phase 19 connector authority and must not be simulated.

## Recommended next entry point

Begin Phase 19.1–19.2 by starting the private Application Fabric endpoint and
composing the registry/broker. Then route a read-only file task and a VS Code
action through the same gateway so Python and application postconditions can
close Phase 18.6 with installed evidence.
