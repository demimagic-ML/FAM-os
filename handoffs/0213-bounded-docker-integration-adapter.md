# Handoff 0213: Bounded Docker integration adapter

**Date:** 2026-07-19  
**Plan step:** Phase 27.13  
**Status:** Partial  
**Previous handoff:** `0212-integration-environment-contracts-and-admission.md`

## Objective

Implement and physically exercise a fail-closed container environment behind
the declarative Core boundary.

## Scope completed

- Added a root-owned executable check and bounded no-shell Docker client.
- Added digest-pinned cached-image launch with no pulls, internal networking,
  read-only root, no-new-privileges, reduced capabilities, PID/memory/CPU
  bounds, and tmpfs-backed writable volumes.
- Added symlink-rejected measured read-only candidate mounts.
- Added ephemeral file-based secret injection; plaintext is absent from argv,
  client environment, receipts, and Docker daemon environment metadata.
- Added durable exclusive runtime claims, immediate network/container identity
  recording, replay denial, partial-failure cleanup, exact cleanup, and restart
  reconciliation.
- Added signed health-recipe support and physically qualified cached
  `postgres:17-alpine` content ID
  `742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`.
- Verified no labeled container or network remained after the real run.

## Explicitly not completed

- Loopback publication while external egress remains denied.
- External hostname allowlist enforcement.
- Retained writable-volume export or retained log artifacts.
- Process/API/browser/local-cluster adapters and product owner controls.
- Signed installed or both-profile qualification.
- Phase 27.13 exit gate.

## Architecture and decisions

ADR 0184 selects internal Docker networks, tmpfs writable volumes, and ephemeral
file-based secret injection. ADR 0183 remains the Core authority and cleanup
policy.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/docker_client.py` | Bounded Docker command execution |
| `src/fam_os/adapters/integration/docker_environment.py` | Environment lifecycle and reconciliation |
| `src/fam_os/adapters/integration/docker_service.py` | Per-service launch, secrets, ports, and health |
| `src/fam_os/adapters/integration/docker_state.py` | Durable replay-resistant runtime claims |
| `src/fam_os/adapters/integration/docker_support.py` | Path, digest, output, and dependency helpers |
| `tests/unit/test_docker_integration_environment.py` | Hostile and lifecycle unit coverage |
| `tests/integration/test_docker_integration_environment.py` | Real cached PostgreSQL container evidence |

## Validation

```bash
PYTHONPATH=src python3 -W error::ResourceWarning -m unittest \
  tests.unit.test_docker_integration_environment \
  tests.integration.test_docker_integration_environment \
  tests.unit.test_integration_environment \
  tests.unit.test_integration_environment_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility
```

Result: 39 tests passed in 2.47 seconds, including the real Docker run.

```bash
PYTHONPATH=src python3 -m unittest discover \
  -s tests/architecture -p 'test_*boundary.py'
```

Result: all 39 architecture tests passed.

## Failed experiments retained as findings

- Docker's `--internal` network returned no published host port. The adapter
  cleaned the container/network and the limitation remains explicit.
- A one-PID fixture caused `tini` to fail its fork. The physical plan was
  corrected to an explicit 64-PID bound; no limit was silently disabled.
- Environment-variable secret injection was rejected during review before
  acceptance because Docker persists it in `.Config.Env`; file injection
  replaced it and the real test inspects metadata for plaintext absence.

## Known limitations and risks

- The compatibility capability set is broader than a service-specific set;
  signed image policy should eventually declare exact required capabilities.
- Docker daemon authority remains a powerful local adapter dependency and must
  only be reachable from the installed unprivileged service composition.
- Signed recipe identity is checked by the injected trusted runner; product
  composition must not accept model-provided runner implementations.

## Recommended next entry point

Compose this adapter with the persistent owner authorizer and a release-owned
health-recipe registry, then add an installed signed PostgreSQL integration
scenario. Use the internal container address through an adapter-only connection
channel rather than weakening egress isolation for host port publication.
