# ADR 0183: Integration environments are declarative, permitted, and cleanup-safe

Status: Accepted

## Context

Tests and database workflows need services, APIs, real browsers, containers,
and local clusters. Allowing a model or Core to assemble raw process or Docker
commands would bypass signed recipes, owner authority, candidate isolation,
resource budgets, and cleanup. Treating teardown as an ordinary mutation would
also let revocation strand FAM-owned processes, networks, and volumes.

## Decision

Core accepts a strict `IntegrationEnvironmentPlan` that binds every service to
the task, candidate, approved changeset, exact host, expiry, and one cumulative
resource impact. Process/API/browser services name a signed launch recipe;
container and cluster services name an exact image reference and image SHA-256.
The same plan declares argv values, loopback-only ports, candidate-relative
volumes, health checks, dependencies, secret references, network mode and
hosts, retained artifacts, and mandatory cleanup.

Core derives exact authorization requests rather than trusting a declared
authority list: one `EXECUTE` request, one `NETWORK` request per allowed host,
and one `SECRET_USE` request per opaque secret reference. A five-minute permit
binds the allowed decision identities, environment, changeset, and host.
Cancellation or plan expiry fails before authorization or executor effects;
live authority is rechecked while the environment starts.

Executor receipts must bind the exact environment and permit. They record
runtime identities, allocated loopback ports, image digests, health evidence,
retained artifact digests, status, and cleanup evidence.

Cleanup is an authority-reducing safety operation over exact original plan,
candidate, permit, and trusted receipt identities. It remains available after
permit expiry or grant revocation, but cannot target an unrelated environment.
An executor must clean partial resources internally if launch fails before it
can return a receipt.

## Consequences

- Core never receives a raw container session or shell command.
- Image tags alone cannot satisfy container admission.
- External network and opaque secret use remain separately owner-granted.
- Revocation stops future/live effects without preventing safe teardown.
- Concrete Docker/process/browser adapters, restart reconciliation, installed
  qualification, and owner controls remain required before Phase 27.13 can be
  claimed.

## Evidence

- `src/fam_os/core/engineering/integration_environment.py`
- `src/fam_os/core/engineering/integration_environment_receipts.py`
- `src/fam_os/core/engineering/integration_environment_ports.py`
- `src/fam_os/core/engineering/integration_environment_service.py`
- `tests/unit/test_integration_environment.py`
- `tests/unit/test_integration_environment_service.py`
- `tests/contract/schema_integration_environment_fixtures.py`
