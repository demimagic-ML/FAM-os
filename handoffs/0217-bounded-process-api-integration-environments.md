# Handoff 0217: Bounded process and API integration environments

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 process/API adapter  
**Status:** Partial  
**Previous handoff:** `0216-persistent-owner-integration-environments.md`

## Objective

Add real no-shell process and loopback API environments behind the existing
Core permit, persistent lifecycle, and owner-control boundary.

## Scope completed

- Added immutable-root trusted clients for systemd-run, systemctl, and Bubblewrap.
- Required exact signed recipe coordinates and exact signed argv.
- Added Bubblewrap candidate isolation inside cgroup- and network-bounded user scopes.
- Added TCP, HTTP, and active-scope health with live revocation/cancellation checks.
- Added candidate-local exact scope state, bounded cleanup, restart reconciliation,
  fresh receipt IDs, and replay denial.
- Added provider-neutral homogeneous Docker versus process/API routing.
- Ran a real Python HTTP API on loopback and verified cgroup values, health,
  cleanup, and zero leftover FAM process scopes.
- Preserved failed transient-service and stop-timeout experiments in ADR 0186.

## Explicitly not completed

- Release-installed trusted process recipe catalog composition.
- Browser, mixed-backend local cluster, Kubernetes, retained-artifact, volume,
  secret, dynamic-port, or allowlisted-egress support.
- Signed installed and both-profile process/API qualification.

## Architecture and decisions

ADR 0186 chooses a transient user scope because this host permits Bubblewrap
user namespaces from the caller-owned scope but denies their UID map from a
manager-spawned transient service. Core and product code remain provider-neutral.
The adapter never accepts arbitrary argv: the plan must exactly match a recipe
already admitted by the signed catalog.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/process_client.py` | Trusted bounded process control client |
| `src/fam_os/adapters/integration/process_state.py` | Durable exact-scope recovery state |
| `src/fam_os/adapters/integration/process_environment.py` | Process/API launch, health, cleanup, reconcile |
| `src/fam_os/adapters/integration/environment_router.py` | Provider-neutral backend routing |
| `src/fam_os/product/composition/integration_environment.py` | Optional trusted process backend composition |
| `tests/unit/test_process_integration_environment.py` | Command, denial, and cleanup fixtures |
| `tests/integration/test_process_api_integration_environment.py` | Real bounded loopback API |
| `tests/unit/test_integration_environment_router.py` | Backend selection and fail-closed mixing |

## Public interfaces

- `ProcessCommandClient`
- `ProcessIntegrationEnvironmentAdapter`
- `IntegrationEnvironmentExecutorRouter`
- Optional `process_recipes` product composition input

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_integration_environment_router \
  tests.unit.test_integration_environment_composition \
  tests.unit.test_process_integration_environment \
  tests.integration.test_process_api_integration_environment \
  tests.unit.test_docker_integration_environment \
  tests.integration.test_docker_integration_environment

PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .
```

Result: the final Docker/process/router aggregate passed 14 tests in 5.790
seconds. The real process/API scenario left zero `fam-process-*.scope` units.
Architecture passes 41 tests.

## Evidence and artifacts

- `docs/decisions/0186-process-api-environments-use-signed-recipes-in-bounded-user-scopes.md`
- Larry run logs under the repository run-log location.

## Known limitations and risks

- Product startup has no release-installed recipe catalog yet, so production
  process routing remains unavailable unless a trusted catalog is injected.
- Port allocation is pre-admission only; requested port zero fails closed.
- The process candidate is writable by the service. Changes remain bounded to
  the candidate and are subject to later changeset verification.
- Mixed Docker/process dependency graphs cannot yet compensate atomically.

## Operational notes

The real test uses only transient owner scopes. `systemctl --user list-units
'fam-process-*.scope' --all` must show zero units after validation.

## Recommended next entry point

Package and load signed release process recipes through the installed trust
root, then extend signed installed qualification through Console/Shell start,
restart reconciliation, and both declared validation profiles.
