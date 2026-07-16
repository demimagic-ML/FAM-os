# Handoff 0060: Context-memory estimation

**Date:** 2026-07-16  
**Plan step:** Phase 7.2  
**Status:** Complete  
**Previous handoff:** `0059-live-scheduler-resource-observation.md`

## Objective

Estimate request-owned context memory independently from model weights for every
current expert execution strategy, preserving capacity, concurrency, output
growth, conservative assumptions, and real local model metadata.

## Scope completed

- Published strict context profile, reservation, and estimate roots.
- Added GQA-aware prompt/output KV estimation for autoregressive models.
- Added hidden-buffer plus quadratic attention peak estimation for encoders.
- Added exact sequence concurrency, fixed/per-sequence workspace, integer-ceiling
  safety margin, and package context-capacity enforcement.
- Required every estimate to exclude model resident bytes structurally.
- Added a read-only Ollama `/api/show` profile adapter with explicit metadata
  fallbacks and no automatic sliding-window discount.
- Bound the five reference entries to exact current package model refs, context
  ceilings, and runtime-contract-derived strategies through integration tests.
- Captured strict local profiles/reservations/estimates for Llama, Qwen, Nomic,
  Laguna, and Gemma without loading or modifying a model.

## Explicitly not completed

- A weight-only resident-memory contract remains necessary before Phase 7.4 can
  combine model and context admission without using context-inflated history.
- Empirical calibration profiles are supported by source identity but were not
  fabricated from metadata. Later replay may replace conservative assumptions
  only with controlled measurements.
- Residency lifecycle transitions are Phase 7.3.
- CPU/GPU split placement is Phase 7.6.

## Architecture and decisions

ADR 0059 separates autoregressive KV growth from encoder activation memory and
separates both from immutable weights. The scheduler owns arithmetic and policy;
Ollama only observes provider metadata. Missing topology expands a conservative
bound or fails closed and is always exposed through assumption codes.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/context_contracts.py` | Strict profile/reservation/estimate contracts. |
| `src/fam_os/scheduler/context_estimator.py` | Pure strategy-specific estimator. |
| `src/fam_os/adapters/ollama/context_profile.py` | `/api/show` metadata adapter. |
| `configs/context_profiles/reference-models.json` | Current package ceilings and reference reservations. |
| `tools/capture_context_memory_estimates.py` | Strict live metadata evidence capture. |
| `tests/unit/test_context_memory_estimator.py` | Formula, growth, concurrency, and failure tests. |
| `tests/unit/test_ollama_context_profile.py` | Metadata/fallback/transport tests. |
| `tests/integration/test_reference_context_profiles.py` | Package/binding/config/evidence drift gate. |
| `tests/contract/schema_scheduler_fixtures.py` | Three new schema representatives. |
| `docs/protocols/CONTEXT_MEMORY_ESTIMATION.md` | Formula, assumptions, and evidence. |
| `docs/decisions/0059-strategy-specific-context-memory-bounds.md` | Durable strategy decision. |

## Public interfaces

- `CONTEXT_MEMORY_CONTRACT_VERSION`
- `ContextMemoryStrategy`, `ContextProfileSource`
- `ContextMemoryModelProfile`, `ContextMemoryReservation`
- `ContextMemoryEstimate`, `ContextMemoryEstimator`
- `OllamaContextProfilePolicy`, `OllamaContextProfileObserver`
- `parse_ollama_context_profile`
- `fam.scheduler.context-profile/v1alpha1`
- `fam.scheduler.context-reservation/v1alpha1`
- `fam.scheduler.context-estimate/v1alpha1`
- `tools/capture_context_memory_estimates.py`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 -m compileall -q src tests tools
python3 <AST implementation file/function size gate>
PYTHONPATH=src:. python3 <strict reference context artifact gate>
larry index
codebase-memory-mcp index_repository full
```

Result: both Python environments passed 625 tests with three expected
environment-dependent skips. All 55 strict schemas and compileall passed. The
size gate checked 360 source/tool Python files and found no file above 300 lines
and no function above 50 lines. The evidence gate decoded 15 strict documents:
five profiles, five reservations, and five estimates, all excluding resident
weights and including both `laguna-xs.2:q4_K_M` and `gemma4:26b`. Larry refreshed
984 files / 2,730 symbols to 16,618 nodes / 55,177 edges. The independent code
graph refreshed to 16,652 nodes / 55,331 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.2/reference-context-estimates/`
- `schemas/v1alpha1/fam.scheduler.context-profile.schema.json`
- `schemas/v1alpha1/fam.scheduler.context-reservation.schema.json`
- `schemas/v1alpha1/fam.scheduler.context-estimate.schema.json`
- `docs/decisions/0059-strategy-specific-context-memory-bounds.md`

## Known limitations and risks

- Reference fixed/workspace overheads are conservative declared policy bounds,
  not measured calibration coefficients.
- Gemma metadata lacks KV-head count and a usable sliding-window layer pattern;
  the resulting 6,710,886,400-byte 5,120-token bound is intentionally high.
- Laguna attention-head count is absent; explicit KV heads and key/value widths
  still permit the KV calculation while retaining the fallback assumption.
- Encoder attention uses a full score-matrix peak and may overestimate optimized
  kernels, but does not claim a runtime-specific optimization.

## Operational notes

The evidence capture called local `/api/show` only. It did not run inference,
load, unload, download, copy, modify, or delete any model. Nomic happened to be
resident in the user's Ollama service before capture and was left untouched.

## Recommended next entry point

Begin Phase 7.3. Read this handoff, `live_contracts.py`, current Ollama loaded
model/unload semantics, package lifecycle state, and runtime bindings. Define a
durable provider-neutral cold/warm/active/evicting state machine with observed
residency reconciliation before implementing admission or eviction policy.
