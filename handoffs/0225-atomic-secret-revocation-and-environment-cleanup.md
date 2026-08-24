# Handoff 0225: Atomic secret revocation and environment cleanup

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 production secret-reference lifecycle  
**Status:** Partial  
**Previous handoff:** `0224-owner-encrypted-engineering-secrets.md`

## Objective

Close the active-materialization gap so owner-authorized secret rotation or
deletion cannot return successfully while a product-managed environment still
uses the previous value.

## Scope completed

- Added one mandatory re-entrant product lifecycle coordinator.
- Serialized environment start through durable active-state persistence with
  secret rotation/deletion through exact cleanup and mutation commit.
- Drained only active plans that declare the exact opaque reference.
- Made any cleanup failure prevent the secret record mutation.
- Added a persistence-backed fail-closed facade for adapter-unavailable hosts.
- Wired the coordinator into production environment and secret composition.
- Added a threaded regression proving rotation cannot miss an in-flight start.
- Added a real Console-authorized rotation test proving scope stop, terminal
  cleanup evidence, exact secret-root erasure, and generation advance.
- Produced signed installed attempt 10 from a fresh wheel for both required
  same-host profile labels.

## Explicitly not completed

- Mixed-backend clusters and allowlisted egress.
- Portable release-owned browser packaging.
- External secret brokers or automatic provider-side credential rotation.
- Independently enforced physical profiles, the two-host gate, 24-hour soak,
  and independent human review.

## Architecture and decisions

ADR 0192 makes lifecycle coordination mandatory and defines cleanup-before-
mutation ordering. ADR 0191 remains authoritative for encrypted owner storage
and metadata-only surfaces; ADR 0190 remains authoritative for file lifetime.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/engineering_secret_lifecycle.py` | Shared lock, exact drain, fail-closed unavailable facade |
| `src/fam_os/product/engineering_secret_api.py` | Cleanup-before-rotate/delete policy |
| `src/fam_os/product/integration_environment_api.py` | Serialized start and terminal transitions |
| `src/fam_os/product/composition/integration_environment.py` | Coordinator composition |
| `src/fam_os/product/service.py` | Mandatory production wiring |
| `tests/unit/test_engineering_secret_api.py` | Exact drain and failed-mutation tests |
| `tests/unit/test_product_integration_environment_api.py` | In-flight start race regression |
| `tests/integration/test_installed_process_owner_restart_chain.py` | Real rotation and cleanup chain |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt10.json` | Signed installed evidence |

## Public interfaces

- `EngineeringSecretLifecycleCoordinator.locked()` serializes materialization
  and retirement; `drain_reference()` performs exact active cleanup.
- `ProductEngineeringSecretApi` now requires both the coordinator and an
  environment lifecycle facade.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_engineering_secret_api \
  tests.unit.test_product_integration_environment_api \
  tests.unit.test_integration_environment_composition \
  tests.integration.test_console_engineering_secrets \
  tests.unit.test_fam_shell_engineering_secret_transport \
  tests.integration.test_installed_process_owner_restart_chain

PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt10.json \
  --repository . --builder-python .verification-venv/bin/python
```

Result: 48 broader lifecycle, storage, transport, coverage, and schema tests
passed in 10.375 seconds; the two real installed process chains independently
passed in 3.261 seconds; all 41 architecture tests passed in 0.767 seconds.
Installed attempt 10 passed 47 tests per
same-host profile label in 48.517248 seconds without checkout imports. Wheel
SHA-256: `c92e48c6a38e53a76e9f53a874d0c57fd9b629e27116614906ad8045d9df7dcc`.
Signer-key SHA-256:
`1cfd65fff7a3261d26095412a26f1123762dced3c88e97c35ad0ef435482b91c`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt10.json`
- `docs/decisions/0192-secret-rotation-and-deletion-drain-active-environments-atomically.md`

## Known limitations and risks

- The coordinator is process-local and assumes the single owner product
  service is the only writer to these repositories.
- Same-UID host processes remain in the owner trust boundary.
- Same-host profile labels are not independent physical evidence.
- Qualification uses an ephemeral signer.

## Operational notes

Qualification left no `fam-int-*` scope or process secret root.

## Recommended next entry point

Implement bounded mixed-backend orchestration or exact allowlisted egress,
then extend the signed installed matrix with positive and negative fixtures.
