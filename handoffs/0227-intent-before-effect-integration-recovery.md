# Handoff 0227: Intent-before-effect integration recovery

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 interrupted launch recovery  
**Status:** Partial  
**Previous handoff:** `0226-journaled-mixed-integration-environments.md`

## Objective

Make every integration launch discoverable before runtime effects and recover
pre-result interruptions without broad host scanning or false cleanup claims.

## Scope completed

- Added migration 0032 for encrypted owner start intents, permits, states, and
  terminal recovery receipts.
- Persisted exact plan/candidate before authorization and exact permit before
  executor entry through a replaceable Core observer.
- Atomically linked successful start commit to its durable intent.
- Distinguished effect-free prelaunch failures from permitted recovery-required
  interruptions.
- Added product startup recovery before normal active-environment reconciliation.
- Added deterministic Docker container/network probing.
- Added deterministic process scope and secret-root probing in a focused module.
- Added mixed recovery for unmarked, partial, failed-cleaned, and ready branches.
- Preserved evidence-backed partial progress and retried only unfinished work.
- Included pending secret consumers in atomic rotation/deletion drain policy.
- Made adapter-unavailable pending recovery deny matching secret mutation.
- Split intent persistence and process recovery into single-purpose modules so
  implementation files remain below the project size targets.
- Changed the real installed mixed scenario to persist intent+permit, omit
  normal result commit, reopen storage, recover both runtimes, and store the
  encrypted terminal recovery receipt.

## Explicitly not completed

- Console/Shell list, inspect, or audit controls for start-intent history.
- Allowlisted egress and a shared cross-backend service network.
- Portable release-owned browser packaging.
- Independently enforced physical profiles, two-host evidence, 24-hour soak,
  and independent human review.

## Architecture and decisions

ADR 0194 resolves ADR 0193's product orphan-discovery limitation with durable
intent-before-effect ordering and deterministic, evidence-labeled recovery.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/storage/migrations/0032_integration_start_intents.sql` | Durable intent schema |
| `src/fam_os/product/storage/integration_start_intent_repository.py` | Encrypted intent transitions |
| `src/fam_os/product/storage/integration_environment_repository.py` | Normal commit linkage/delegation |
| `src/fam_os/core/engineering/integration_environment_service.py` | Permit observer before executor |
| `src/fam_os/product/integration_environment_api.py` | Begin, interrupt, recover, startup policy |
| `src/fam_os/product/composition/integration_environment.py` | Recovery-before-active composition |
| `src/fam_os/adapters/integration/docker_environment.py` | Exact interrupted Docker recovery |
| `src/fam_os/adapters/integration/process_recovery.py` | Exact process/secret recovery |
| `src/fam_os/adapters/integration/process_environment.py` | Recovery delegation |
| `src/fam_os/adapters/integration/composite_environment.py` | All-branch interrupted recovery |
| `src/fam_os/adapters/integration/environment_router.py` | Provider-neutral recovery dispatch |
| `src/fam_os/product/engineering_secret_lifecycle.py` | Pending-consumer drain/fail closed |
| `tests/integration/test_real_mixed_integration_environment.py` | Real pre-result recovery chain |
| `tools/run_phase27_integration_environment_qualification.py` | Installed recovery scenarios |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt13.json` | Signed installed evidence |

## Public interfaces

- `IntegrationEnvironmentService.start(..., permit_observer=None)` calls the
  observer after permit minting and before executor launch.
- `ProductIntegrationEnvironmentApi.pending()` and `recover_pending()` expose
  owner-scoped internal lifecycle operations used by secret retirement.
- Concrete integration executors now implement deterministic `recover()`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest <phase-27 affected modules and coverage>
PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check

PYTHONPATH=src .verification-venv/bin/python -m unittest \
  tests.integration.test_product_service_storage_modes \
  tests.unit.test_product_service_startup_safety \
  tests.integration.test_product_service

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt13.json \
  --repository . --builder-python .verification-venv/bin/python
```

Result: 97 affected lifecycle, storage, transport, physical, coverage, and
schema tests passed in 27.646 seconds; all 41 architecture tests passed in
0.737 seconds; 371 schemas validated. Seven product startup/storage tests
passed in the verification environment in 4.448 seconds. Installed attempt 13
passed 67 tests per same-host profile label in 58.886605 seconds without
checkout imports. Wheel SHA-256:
`a8196339fe2a551844103d6dec37861ca149730176ec4c821a9f58ac290bc11d`.
Signer-key SHA-256:
`e10b2bc0d053f264c0c93b5a4dd7ac49dccb4aba040bd20abe4fe08aa96d3ac1`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt13.json`
- `docs/decisions/0194-integration-launch-intent-and-permit-precede-runtime-effects.md`

## Known limitations and risks

- Start-intent recovery evidence is encrypted and durable but not yet visible
  through Console or Shell.
- Deterministic negative probes establish absence at the checked exact identity;
  they do not claim a resource was previously observed.
- Same-UID candidate state remains inside the current owner trust boundary.
- Same-host profile labels are not independent physical evidence.
- Qualification uses an ephemeral signer.

## Operational notes

Qualification left no labeled FAM container/network, process scope, temporary
build root, or process secret root.

## Recommended next entry point

Add metadata-only Console and strict Shell list/inspect/audit surfaces for start
intents and their recovery receipts. Then resume allowlisted egress or portable
browser packaging.
