# Handoff 0172: Production resource and operating-policy wiring

**Date:** 2026-07-18  
**Plan step:** Phase 23 audit correction for Phases 7.1, 7.10, 11.4, and 18.5  
**Status:** Complete  
**Previous handoff:** `0171-console-workspace-context-and-secure-launch.md`

## Objective

Remove the installed product's `MemAvailable + free VRAM` shortcut and make
local selection and predictive prewarming obey the already-approved resource
and operating-state policies.

## Scope completed

- Added bounded Linux observation for system battery, hottest sysfs/NVIDIA
  temperature, normalized host load, and GNOME desktop idle time.
- Projected full/compatibility host and VRAM reserves into one production
  capacity contract.
- Added the managed Ollama cgroup allocation ceiling and fail-closed unknown
  managed usage.
- Applied maximum expert tier to cold and resident candidates, including
  explicit escalation requests.
- Required both speculation and idle-background authority before predictive
  prewarming and retained the no-eviction invariant.
- Preserved explicit external-Ollama operation without fabricating cgroup
  enforcement.
- Made unknown thermal state serializable and fail-safe for speculation.

## Explicitly not completed

- Durable production cold/warm/active/evicting residency and confirmed eviction
  are not composed into the task worker yet.
- No other Ollama model is automatically unloaded because active cross-request
  leases do not yet protect in-flight inference.
- This source correction has not yet passed a freshly built signed release
  matrix or the 24-hour Phase 23 soak.

## Architecture and decisions

ADR 0148 records the production composition rule. One capacity observer is
shared by request selection and live prewarming so those paths cannot disagree.
Profile reserves remain distinct from current availability, and the managed
cgroup ceiling is an additional clamp rather than a replacement for OS
headroom. Resource uncertainty can deny cold allocation without pretending an
already resident expert needs to be allocated again.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/linux/operating_state.py` | Bounded live operating-state probe. |
| `src/fam_os/adaptation/resource_policy.py` | Explicit unknown thermal policy. |
| `src/fam_os/core/production/model_selection.py` | Schedulable capacity, tier caps, and reasons. |
| `src/fam_os/product/composition/live_capacity.py` | Production policy and cgroup projection. |
| `src/fam_os/product/composition/runtime_unit.py` | Managed Ollama resource snapshot. |
| `src/fam_os/product/live_model_prewarm.py` | Background/speculation/tier admission. |
| `src/fam_os/product/service.py` | Shared production observer composition. |
| `schemas/v1alpha1/fam.adaptation.operating-state.schema.json` | Nullable unknown thermal reading. |
| `docs/protocols/OPERATING_STATE_ADAPTATION.md` | Installed semantics and limits. |
| `docs/decisions/0148-production-selection-observes-resource-and-operating-policy.md` | Accepted production boundary. |

## Public interfaces

`HostCapacity` now exposes explicit reserves, a managed host allocation ceiling,
schedulable host/VRAM properties, a maximum expert tier, background/speculation
permissions, and decision reason codes. Existing two-argument construction
retains the previous 2 GiB host reserve.

## Validation

```bash
.verification-venv/bin/python -m unittest \
  tests.unit.test_linux_operating_state \
  tests.unit.test_product_live_capacity \
  tests.unit.test_operating_state_policy \
  tests.unit.test_production_model_policy \
  tests.unit.test_product_live_adaptation
larry run ".verification-venv/bin/python -m unittest tests.integration.test_product_service tests.unit.test_production_task_gateway tests.unit.test_product_service_cli tests.unit.test_managed_ollama_service tests.unit.test_live_resource_sampler tests.unit.test_configuration_layering tests.unit.test_effective_resource_budget_schema tests.contract.test_schema_compatibility"
.verification-venv/bin/python tools/render_contract_schemas.py --check
```

Result: 22 focused tests and 75 composition/blast-radius tests passed. Ruff
passed on every changed Python file. All 285 schema artifacts validated.

## Evidence and artifacts

- `tests/unit/test_linux_operating_state.py`
- `tests/unit/test_product_live_capacity.py`
- `tests/unit/test_production_model_policy.py`
- `tests/unit/test_product_live_adaptation.py`
- ADR 0148

## Known limitations and risks

- One-minute host load is a conservative pressure approximation, not per-window
  process attribution.
- External Ollama cannot provide a FAM-owned cgroup ceiling.
- Production residency/eviction is still the next confirmed integration gap.

## Operational notes

On the current full workstation, the live observer detected the full profile,
retained 12 GiB host and 1 GiB VRAM reserves, permitted escalation, and permitted
idle background work. Exact available bytes vary with resident Ollama models
and are intentionally sampled per decision.

## Recommended next entry point

Audit production execution leases and residency coordination before connecting
Phase 7 eviction. Start with `src/fam_os/core/production/execution_worker.py`,
`src/fam_os/scheduler/residency.py`, and the Ollama confirmed-unload adapter.
