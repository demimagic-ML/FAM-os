# Handoff 0148: Production live predictive adaptation

**Date:** 2026-07-17  
**Plan step:** Phase 20.6  
**Status:** Complete  
**Previous handoff:** `0147-production-verified-outcome-learning.md`

## Objective

Connect verified production learning to live expert frequency, context,
escalation, and next-expert prewarm behavior without changing permission,
verification, or acceptance policy.

## Scope completed

- Added strict content-free live snapshot and prewarm receipt contracts plus two
  generated schemas.
- Added migration 0014 and an owner-encrypted repository for immutable snapshots
  and completed, rejected, or failed prewarm receipts.
- Derived P95 context, escalation probability, unique-leader frequency, and
  transition predictions only from verified local Phase 20.5 records.
- Applied a conservative complete-prompt context lower bound; images retain full
  context and verifier feedback raises the bound when necessary.
- Added advisory frequency ordering inside the existing signed intent-compatible
  policy tier.
- Corrected strong escalation ordering so resident primary models cannot defeat
  the declared escalation tier.
- Added asynchronous, restart-reconstructed, resource-admitted model prewarm
  with no prompt, no requested eviction, and confirmed runtime residency.
- Added Ollama prompt-free preload support and post-load `/api/ps` confirmation.
- Proved installed selection, repair, strong escalation, transition prewarm,
  context reduction, unchanged verification quality, encryption, restart, and
  removal with a signed seven-component release.
- Proved real hardware preload and unload for downloaded `gemma4:26b` and
  `laguna-xs.2:q4_K_M` on the RTX 5080 workstation.

## Explicitly not completed

- Phase 20.7 Console and Shell inspection, disable, reset, drift, and rollback.
- Phases 21-23.
- A real-model task-quality benchmark is still part of final Phase 23 matrices;
  the Phase 20.6 installed task gate uses a deterministic residency-aware runtime
  while the separate hardware gate validates actual strong-model loading.

## Architecture and decisions

ADR 0130 keeps adaptation advisory. Predictors cannot manufacture authority,
cross an intent or policy tier, bypass live resource fit, lower context below the
complete active prompt, change a verifier, or release an unverified candidate.
Durable snapshots contain only coarse features and source identities. Prewarm is
an optimization; normal on-demand loading remains the fallback.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/adaptation/live_prediction.py` | Snapshot and prewarm receipt contracts. |
| `src/fam_os/product/live_prediction_builder.py` | Deterministic verified-record derivation. |
| `src/fam_os/product/live_adaptation.py` | Installed advice, context, and asynchronous prewarm. |
| `src/fam_os/product/storage/live_adaptation_repository.py` | Owner-encrypted prediction evidence. |
| `src/fam_os/product/storage/migrations/0014_live_adaptation.sql` | Durable prediction schema. |
| `src/fam_os/core/production/model_selection.py` | Frequency tie and corrected escalation order. |
| `src/fam_os/core/production/execution_worker.py` | Complete-prompt context application. |
| `src/fam_os/adapters/ollama/runtime.py` | Prompt-free preload and residency proof. |
| `tools/phase20_live_exit/` | Signed installed qualification processes. |
| `tools/run_phase20_hardware_prewarm.py` | Physical strong-model preload gate. |

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.verification-venv/bin/python -m unittest discover -s tests/architecture -p 'test_*.py'
.verification-venv/bin/python -m unittest discover -s tests/contract -p 'test_*.py'
.verification-venv/bin/ruff check src tests tools
.verification-venv/bin/mypy <11 affected source targets>
.verification-venv/bin/python tools/render_contract_schemas.py --check
.verification-venv/bin/python tools/run_phase20_live_adaptation_exit.py
.verification-venv/bin/python tools/run_phase20_hardware_prewarm.py
git diff --check
```

Results: 990 tests pass with two declared skips; 39 architecture tests, 35
contract tests, 11 affected Mypy targets, whole-tree Ruff, and 202 generated
schema artifacts pass. The signed installed artifact reports `passed: true` with
a 32,768 to 2,048 repeated context reduction and unchanged verified quality.
The physical artifact reports `passed: true`; Gemma used 12,251,100,609
accelerator bytes and Laguna used 13,479,025,049 accelerator bytes, and both
were confirmed unloaded afterward.

## Evidence

- `artifacts/adaptation/phase20.6-live-adaptation.json`
- `artifacts/adaptation/phase20.6-hardware-prewarm.json`
- `tests/unit/test_product_live_adaptation.py`
- `tests/unit/test_production_model_policy.py`
- `tests/unit/test_production_task_gateway.py`
- `tests/unit/test_ollama_runtime.py`
- `docs/decisions/0130-live-adaptation-is-advisory-and-verification-invariant.md`

## Known limitations and risks

- Phase 20.7 controls are not yet reachable from Shell or Console.
- The context floor uses conservative UTF-8 byte accounting rather than a
  provider tokenizer; it intentionally over-reserves short text.
- Background prewarm depends on provider load cancellation semantics during
  shutdown; no task or acceptance depends on prewarm completion.
- The physical gate validates loading, residency, and unload, not answer quality.

## Recommended next entry point

Begin Phase 20.7 from `ProductLiveAdaptation.snapshots()`, `receipts()`, existing
`AdaptationDriftPolicy`, Shell memory-control patterns, and Console management
routes. Add owner-visible status first, then confirmed disable/reset, then
quality/thermal/policy drift rollback with installed evidence.
