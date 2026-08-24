# Handoff 0136: Installed unified Core gateway

**Date:** 2026-07-17  
**Plan steps:** Phase 18.1–18.2; partial 18.3–18.8  
**Status:** Complete for the stated slice  
**Previous handoff:** `0135-signed-complete-release-installation.md`

## Scope completed

- Replaced the production fixed-model gateway with one durable admission,
  routing, immutable-plan, inference, verification, and final-result path.
- Added policy-owned intent classification for conversation, grounded, read,
  mutation, code, math, retrieval, media, and administration categories.
- Added encrypted restart-safe inference records and migration 0006.
- Added a seven-model release catalog bound to live Ollama manifest digests and
  artifact sizes, plus live RAM/VRAM selection and digest-validated activation.
- Added exact-output verification, one feedback-bound repair, one strong
  escalation, and a durable shared repair/escalation budget.
- Added explicit unverified/verified assurance evidence. Requests without a
  declared verifier are withheld when verification is required.

## Installed evidence

The signed `phase18-unified` release was installed from its offline wheelhouse.
A task was admitted, the product service was stopped before inference, managed
Ollama became inactive, and the same session completed after service restart.
An independent installed request returned `VERIFIED_READY` with candidate and
verification evidence. See
`artifacts/product/phase18/unified-installed-core.json`.

## Validation

- 883 tests pass; seven declared environment skips.
- 184 public schemas render and round-trip.
- Ruff and mypy pass for the new production modules.
- Live selection observed qwen3:1.7b for conversation,
  qwen2.5-coder:7b for code, and both Laguna and Gemma 26B fitting the current
  combined host/VRAM budget.

## Remaining gaps

- Validate catalog entries through enabled per-package trust and lifecycle
  state, not only the signed release and Ollama manifest digest.
- Bind Python, retrieval, math, media, and application postcondition verifiers
  into this gateway. The exact-output verifier is intentionally narrow.
- Use live Ollama residency/eviction state and measured placement outcomes.
- Persist and expose grounded assurance, richer selection explanations, and
  all task events to Console.
- Prove approval and uncertain application-action restart through the installed
  gateway in Phase 19.

## Recommended next entry point

Continue Phase 18.3 by composing signed package installation state and runtime
bindings into the live catalog, then bind the Python verifier and exact repair
context to the stable-topological-sort workflow before beginning Application
Fabric production composition.
