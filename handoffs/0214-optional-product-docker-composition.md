# Handoff 0214: Optional product Docker composition

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 production composition  
**Status:** Partial  
**Previous handoff:** `0213-bounded-docker-integration-adapter.md`

## Objective

Compose the bounded container adapter into the installed product without making
Docker or unprovisioned secrets mandatory dependencies.

## Scope completed

- Added an optional product integration-environment unit sharing the persistent
  engineering authorizer.
- Required a real immutable root-owned Docker executable; missing or untrusted
  executables degrade to an unavailable optional capability rather than
  preventing product startup.
- Added one release-owned PostgreSQL `pg_isready` health recipe with exact argv.
- Added a deny-by-default product secret injector: secret-free plans can run,
  while every referenced secret fails until a trusted credential provider is
  explicitly composed.
- Reset the optional unit during product shutdown.

## Explicitly not completed

- Product credential provisioning and rotation.
- Console/Shell environment controls and persistent environment catalog.
- Installed signed qualification.
- Other environment kinds and Phase 27.13 exit gate.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/composition/integration_environment.py` | Optional adapter/Core composition and trusted health recipe |
| `src/fam_os/product/service.py` | Product lifecycle composition |
| `tests/unit/test_integration_environment_composition.py` | Availability, degradation, secret, and recipe tests |

## Validation

```bash
PYTHONPATH=src python3 -W error::ResourceWarning -m unittest \
  tests.unit.test_integration_environment_composition \
  tests.unit.test_docker_integration_environment \
  tests.integration.test_docker_integration_environment \
  tests.unit.test_integration_environment \
  tests.unit.test_integration_environment_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility
```

Result: 42 tests passed in 2.48 seconds.

```bash
PYTHONPATH=src python3 -m unittest discover \
  -s tests/architecture -p 'test_*boundary.py'
```

Result: all 39 architecture tests passed.

## Known limitations and risks

- The composed unit is not yet owner-client reachable.
- Docker group access is daemon-level authority; only the bounded adapter may
  receive the client object.
- Secret-bearing services remain intentionally unavailable until Phase 27.16
  provides an adapter-only credential source.

## Recommended next entry point

Build and install a signed wheel and run the real cached PostgreSQL lifecycle
from `site-packages`. Then add a persistent environment catalog and exact owner
start/inspect/cleanup controls without exposing Docker sessions.
