# Handoff 0226: Journaled mixed integration environments

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 mixed service clusters  
**Status:** Partial  
**Previous handoff:** `0225-atomic-secret-revocation-and-environment-cleanup.md`

## Objective

Allow one admitted environment to coordinate bounded Docker and process/API
services without duplicating authority, resource, cleanup, or evidence policy.

## Scope completed

- Added a provider-neutral mixed adapter selected only when both backends exist.
- Derived deterministic backend launch order from service dependencies.
- Denied backend-group cycles that would require unsafe interleaving.
- Partitioned aggregate memory, CPU, and process limits across subplans.
- Recomputed exact private subplan authorities without changing the owner plan.
- Added reverse-order launch compensation and cleanup that continues on errors.
- Added a mode-0600 journal for launched branches and cleanup evidence.
- Made partial cleanup restart-resumable without replaying terminal branches.
- Captured retained artifacts once and assembled one exact combined receipt.
- Added product-composition, missing-backend, compensation, partial recovery,
  resource conservation, cycle, and journal-tamper coverage.
- Proved a real cached digest-pinned Python container dependency plus a
  signed-recipe process API, followed by fresh-adapter restart cleanup.
- Added the mixed unit and physical scenarios to signed installed qualification.

## Explicitly not completed

- Automatic product discovery of `cleanup_required` composite journals created
  when launch compensation fails before a start result is persisted.
- Docker-process-Docker interleaving or a shared cross-backend service network.
- Allowlisted egress and portable release-owned browser packaging.
- Independently enforced physical profiles, two-host evidence, 24-hour soak,
  and independent human review.

## Architecture and decisions

ADR 0193 assigns mixed provider orchestration and restart progress to an adapter
above the concrete Docker/process implementations. Core admission and product
owner lifecycle remain unchanged.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/composite_environment.py` | Partition, order, compensate, reconcile, combine evidence |
| `src/fam_os/adapters/integration/composite_state.py` | Owner-private restart journal |
| `src/fam_os/adapters/integration/environment_router.py` | Mixed selection and missing-backend denial |
| `src/fam_os/adapters/integration/__init__.py` | Public adapter export |
| `tests/unit/test_mixed_integration_environment.py` | Positive and adversarial lifecycle coverage |
| `tests/unit/test_integration_environment_router.py` | Updated provider selection policy |
| `tests/unit/test_integration_environment_composition.py` | Production composition proof |
| `tests/integration/test_real_mixed_integration_environment.py` | Real Docker/process restart chain |
| `tools/run_phase27_integration_environment_qualification.py` | Installed scenarios |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt12.json` | Signed installed evidence |

## Public interfaces

- `MixedIntegrationEnvironmentAdapter`: integration executor contract for
  groupable Docker/process plans.
- `IntegrationEnvironmentExecutorRouter.mixed`: composed mixed executor or
  `None` when either required concrete backend is unavailable.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_mixed_integration_environment \
  tests.unit.test_integration_environment_router \
  tests.unit.test_integration_environment_composition \
  tests.integration.test_real_mixed_integration_environment -v

PYTHONPATH=src python3 -m unittest <phase-27 affected modules and coverage>
PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt12.json \
  --repository . --builder-python .verification-venv/bin/python
```

Result: the focused mixed suite passed 11 tests with its real chain in 4.687
seconds; the broader affected suite passed 82
tests in 27.116 seconds; all 41 architecture tests passed in 0.744 seconds;
371 schemas validated. Installed attempt 12 passed 52 tests per same-host
profile label in 58.082715 seconds without checkout imports. Wheel SHA-256:
`7d0f8e2b3399fb4bfba9d7b9336395f2afa8c047940231ce45b0c6968f422858`.
Signer-key SHA-256:
`ffa2933bd1a47213ae0d423223f8280023df0cb17628687207b0792599f04da9`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt12.json`
- `docs/decisions/0193-mixed-integration-backends-use-a-journaled-composite-lifecycle.md`

## Known limitations and risks

- A double failure during launch and compensation is journaled but is not yet
  discovered by product startup when no active repository record exists.
- Same-UID candidate journal modification is detected but remains inside the
  current single-owner host trust boundary.
- The Docker host does not publish ports from `--internal` networks; the real
  scenario proves readiness ordering and cleanup, not cross-backend traffic.
- Same-host profile labels are not independent physical evidence.
- Qualification uses an ephemeral signer.

## Operational notes

Qualification left no labeled FAM container/network, process scope, temporary
build root, or process secret root.

## Recommended next entry point

Add product startup discovery and exact recovery for orphaned composite journals
whose launch compensation failed before result persistence. Then decide whether
shared cross-backend networking belongs in Phase 27.13 or stays deliberately
unsupported.
