# Handoff 0212: Integration environment contracts and admission

**Date:** 2026-07-19  
**Plan step:** Phase 27.13  
**Status:** Partial  
**Previous handoff:** `0211-installed-database-authority-chain.md`

## Objective

Create the trusted declarative and Core-admission boundary for bounded services,
APIs, browsers, containers, and local clusters.

## Scope completed

- Added exact service, image, argv, port, volume, health, dependency, network,
  secret-reference, artifact, resource, expiry, and cleanup contracts.
- Added four strict schema roots for service specifications, environment plans,
  execution permits, and receipts; total registered roots are now 363.
- Required image SHA-256 for containers and signed launch recipes for local
  processes, APIs, and browsers.
- Restricted host port publication to loopback and required acyclic declared
  service dependencies.
- Added Core derivation of exact execute, per-host network, and per-secret
  authorization requests plus a five-minute decision-bound permit.
- Added live reauthorization, pre-effect cancellation/expiry denial, executor
  receipt identity checks, and exact authority-reducing cleanup.

## Explicitly not completed

- Concrete Docker, process/systemd, browser, or local-cluster adapters.
- Durable restart reconciliation and replay resistance.
- Product composition or Console/Shell controls.
- Installed or physical qualification.
- Phase 27.13 exit gate.

## Architecture and decisions

ADR 0183 defines integration environments as declarative Core plans and keeps
cleanup available after authority loss only for exact FAM-owned identities.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/integration_environment.py` | Plan, service, resource, and permit contracts |
| `src/fam_os/core/engineering/integration_environment_receipts.py` | Runtime, health, artifact, and cleanup evidence |
| `src/fam_os/core/engineering/integration_environment_ports.py` | Replaceable executor boundary |
| `src/fam_os/core/engineering/integration_environment_service.py` | Core authority and lifecycle admission |
| `src/fam_os/core/engineering/__init__.py` | Public contract exports |
| `src/fam_os/schemas/catalog.py` | Four strict schema roots |
| `tests/contract/schema_integration_environment_fixtures.py` | Canonical schema fixtures |
| `tests/unit/test_integration_environment.py` | Contract and hostile-shape tests |
| `tests/unit/test_integration_environment_service.py` | Admission, cancellation, expiry, and cleanup tests |

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_integration_environment \
  tests.unit.test_integration_environment_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility
```

Result: 33 tests passed.

```bash
PYTHONPATH=src python3 -m unittest discover \
  -s tests/architecture -p 'test_*boundary.py'
```

Result: all 39 architecture tests passed.

## Known limitations and risks

- The adapter must verify the local image content ID, not trust the plan's tag.
- Secret injection needs an adapter-only provider; Core and receipts must never
  receive plaintext values.
- Allowlisted external container networking requires a real enforcement
  mechanism; an adapter must fail closed if it cannot enforce the host list.
- Launch failure must clean partial resources even when no receipt can be
  returned.

## Recommended next entry point

Implement a Docker adapter for digest-pinned cached images with internal or
denied networks, loopback ephemeral ports, candidate-confined bind mounts,
bounded health/log collection, durable runtime claims, and restart cleanup.
Qualify it with the cached PostgreSQL image before adding the PostgreSQL
database adapter.
