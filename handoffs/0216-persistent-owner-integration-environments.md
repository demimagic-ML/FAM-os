# Handoff 0216: Persistent owner integration environments

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 durable lifecycle and owner controls  
**Status:** Partial  
**Previous handoff:** `0215-signed-installed-docker-environment.md`

## Objective

Make admitted Docker integration environments discoverable, controllable, and
cleanup-safe across product restarts without automatic relaunch.

## Scope completed

- Added a digest-bound start result carrying the exact Core permit and receipt.
- Added migration 0030 and owner-context encrypted plan, candidate, start,
  latest-receipt, and append-only lifecycle-event storage.
- Added single-use environment IDs, terminal cleanup, replay denial, and fresh
  cleanup receipt identities.
- Added product persistence compensation and conservative startup reconciliation.
- Composed the repository and lifecycle API into `LocalProductService`.
- Added authenticated Console start/list/inspect/audit/cleanup/reconcile routes.
- Added four strict Shell roots and owner-UID Unix-socket dispatch for the same
  operations.
- Preserved fail-closed product degradation when trusted Docker is unavailable.

## Explicitly not completed

- Process, API, browser, local-cluster, or Kubernetes environment adapters.
- Enforceable allowlisted Docker egress, internal-network loopback publication,
  retained-artifact extraction, or product secret provisioning.
- A new signed installed qualification covering the owner surfaces and restart
  repository lifecycle.
- Independently enforced validation profiles or second-host evidence.

## Architecture and decisions

ADR 0185 makes encrypted product storage the source of lifecycle discovery and
the candidate-local Docker state the source of exact runtime identities. Restart
may clean but never relaunch. Cleanup is authority-reducing and remains available
with the original identity chain after grant expiry or revocation. Console and
Shell remain adapters to one product API and never receive Docker primitives.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/integration_environment.py` | Canonical plan digest |
| `src/fam_os/core/engineering/integration_environment_receipts.py` | Permit-bearing start result |
| `src/fam_os/core/engineering/integration_environment_service.py` | Return exact admitted start result |
| `src/fam_os/product/storage/migrations/0030_integration_environments.sql` | Durable lifecycle schema |
| `src/fam_os/product/storage/integration_environment_repository.py` | Encrypted lifecycle repository |
| `src/fam_os/product/integration_environment_api.py` | Owner lifecycle and restart coordination |
| `src/fam_os/product/composition/core_storage.py` | Repository composition |
| `src/fam_os/product/composition/storage_unit.py` | Product repository exposure |
| `src/fam_os/product/composition/integration_environment.py` | Persistent API and startup reconciliation |
| `src/fam_os/product/service.py` | Console and Shell composition |
| `src/fam_os/console/integration_environment_routes.py` | Authenticated owner HTTP controls |
| `src/fam_os/shell/integration_environment_contracts.py` | Strict owner Shell contracts |
| `src/fam_os/adapters/shell/integration_environment_dispatch.py` | Shell lifecycle dispatch |
| `src/fam_os/adapters/integration/docker_environment.py` | Fresh cleanup receipt identity |
| `src/fam_os/schemas/catalog.py` | Five Core/product and four Shell roots |

## Public interfaces

- `IntegrationEnvironmentStartResult`
- `ProductIntegrationEnvironmentApi`
- Console `/api/v1/engineering/environments[...]`
- Shell `integration_environment_start`, `integration_environment_query`, and
  `integration_environment_control` wire kinds
- `fam.shell.integration-environment-*/v1alpha1` schema families
- SQLite migration 0030

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_fam_shell_integration_environment_transport \
  tests.unit.test_fam_shell_engineering_authority_transport \
  tests.integration.test_console_integration_environments \
  tests.integration.test_console_engineering_authority \
  tests.unit.test_product_integration_environment_api \
  tests.unit.test_integration_environment_repository \
  tests.unit.test_integration_environment_composition \
  tests.unit.test_integration_environment \
  tests.unit.test_integration_environment_service \
  tests.unit.test_docker_integration_environment \
  tests.integration.test_docker_integration_environment \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility

PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .
```

Result: the final focused lifecycle, schema, Console, Shell, persistence, and
real-Docker run passed 59 tests in 4.223 seconds. The architecture suite passed
41 tests in 0.740 seconds. The cached PostgreSQL container and internal network
were cleaned by the real test.

## Evidence and artifacts

- `docs/decisions/0185-integration-environments-persist-encrypted-and-reconcile-without-relaunch.md`
- Existing installed Docker artifact:
  `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt1.json`

## Known limitations and risks

- Startup cleanup cannot run while trusted Docker is absent; the active record
  remains encrypted and unresolved.
- Console start is synchronous for bounded health admission.
- Product secrets remain fail-closed, so secret-bearing plans need an explicitly
  composed trusted provider.
- Phase 27.13 remains incomplete until the declared non-Docker environment kinds
  and profile evidence are implemented.

## Operational notes

Migration 0030 is forward-only and is applied by normal secure-storage startup.
No container or network should remain after the real Docker test. Do not delete
candidate `.fam-integration/` state before reconciliation.

## Recommended next entry point

Add a no-shell signed-recipe process/API adapter with the same permit, resource,
health, candidate-state, persistent-recovery, Console, and Shell boundaries;
then extend installed qualification to the complete owner lifecycle.
