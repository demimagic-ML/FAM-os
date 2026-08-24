# Handoff 0173: Production residency and confirmed eviction

**Date:** 2026-07-18  
**Plan step:** Phase 23 audit correction for Phases 7.2–7.4 and 18.5  
**Status:** Complete in source; signed installed qualification remains Phase 23  
**Previous handoff:** `0172-production-resource-policy-wiring.md`

## Objective

Compose Scheduler-owned residency into every installed Ollama consumer so FAM
can use reclaimable warm capacity without unloading a model that inference,
embedding, adaptation, remote work, or the Expert Factory is using.

## Scope completed

- Added one private durable production residency catalog bound to the signed
  runtime catalog and current provider observations.
- Built the first catalog directly from provider evidence; known loaded models
  never pass through a false durable cold state.
- Added restart recovery for leases whose owning process and worker threads no
  longer exist.
- Added autoregressive generation and encoder-activation embedding admission.
- Held request leases through the complete provider call and released them on
  both success and failure.
- Enabled stable warm-only confirmed eviction for managed Ollama.
- Denied eviction for external Ollama rather than touching user-owned models.
- Added reclaimable warm host/VRAM capacity to selection without counting active,
  cold, temporary, or unknown models.
- Routed predictive prewarming, document embedding, remote execution, synthetic
  teachers, and factory canaries through the same serialized runtime facade.
- Added an architecture regression that rejects future raw-runtime bypasses in
  product composition.

## Architecture and decisions

ADR 0149 records the single-facade rule. The main task worker retains the real
Core request ID in its lease. Auxiliary operations receive unique operation IDs.
Temporary canary models are serialized but never inserted into the active
catalog or offered as eviction candidates. Managed and external Ollama remain
explicitly different authority modes.

The provider critical section is intentionally serialized across complete
model calls. This is a throughput tradeoff, not an accidental implementation
detail: explicit eviction is unsafe until concurrent provider operations can
prove model-specific pinning with the same durable lease invariant.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/model_residency.py` | Production admission, leases, facade, and eviction. |
| `src/fam_os/product/service.py` | Single-facade composition for every installed consumer. |
| `src/fam_os/core/production/execution_worker.py` | Request-scoped residency port around local chat. |
| `src/fam_os/core/production/gateway.py` | Residency injection into task workers. |
| `src/fam_os/core/production/model_selection.py` | Explicit reclaimable warm capacity. |
| `src/fam_os/scheduler/residency_contracts.py` | Process-recovery transition reason. |
| `src/fam_os/scheduler/residency_service.py` | Catalog synchronization, observed initialization, and restart recovery. |
| `tests/unit/test_product_model_residency.py` | Production lease, embedding, eviction, restart, and concurrency matrix. |
| `tests/integration/product_runtime_fixture.py` | Protocol-complete product test provider. |
| `tests/architecture/test_product_composition_boundary.py` | No-bypass composition invariant. |
| `docs/protocols/EXPERT_RESIDENCY_LIFECYCLE.md` | Installed lifecycle semantics. |
| `docs/decisions/0149-installed-runtime-uses-one-residency-facade.md` | Accepted boundary. |

## Validation

```bash
.verification-venv/bin/python -m unittest \
  tests.unit.test_product_model_residency \
  tests.unit.test_expert_residency_service \
  tests.unit.test_residency_state_repository

larry run ./.verification-venv/bin/python -m unittest \
  tests.integration.test_product_application_action \
  tests.integration.test_product_application_fabric \
  tests.integration.test_product_mcp_ingress \
  tests.integration.test_product_os_workflows \
  tests.integration.test_product_service \
  tests.integration.test_product_service_storage_modes \
  tests.integration.test_verified_directory_action \
  tests.integration.test_product_remote_execution \
  tests.unit.test_product_live_adaptation \
  tests.unit.test_product_document_index_service \
  tests.unit.test_product_grounded_retrieval \
  tests.unit.test_factory_canary_runner \
  tests.unit.test_factory_release_composition \
  tests.integration.test_console_factory \
  tests.architecture.test_product_composition_boundary

.verification-venv/bin/python tools/render_contract_schemas.py --check
.verification-venv/bin/python -m unittest discover -s tests
```

Result: 28 focused residency/repository tests and 50 product blast-radius tests
passed. The complete source suite passed 1,241 tests with two declared
environment/hardware skips. Repository-wide Ruff passed. All 285 generated
schemas validate.

## Explicitly not completed

- No fresh signed release has yet exercised this source correction.
- No 24-hour installed pressure/restart/rollback soak has yet run.
- Local provider operations remain serialized; concurrent model-specific
  pinning is not claimed.
- External Ollama remains observable but non-evictable by design.

## Recommended next entry point

Run the live external-Ollama request smoke, then continue the Phase 23
phase-by-phase audit. The next audit should distinguish remaining source gaps
from clean-build, signed-install, physical-matrix, soak, review, and removal
evidence gates.
