# ADR 0225: Natural PostgreSQL is a fixed isolated service template

Status: Accepted

## Context

ADR 0224 established a separate exact owner grant for natural integration
network destinations and opaque secret references, but the natural planner
could still compose only release-owned Python API and static-site processes.
The broader integration fabric already had a digest-pinned PostgreSQL 17
Docker proof, a signed `pg_isready` health recipe, encrypted consumer-bound
secret storage, and cleanup/recovery. None of those powers were reachable from
an ordinary natural PostgreSQL request.

Treating an arbitrary image, command, port, environment variable, or
credential named by the model as executable configuration would violate the
fixed-template boundary. Treating successful container startup as remote
database migration support would also overstate the evidence.

## Decision

The public natural integration declaration adds one closed `postgresql` role.
Candidate data may select its bounded logical identity and dependencies, but it
cannot select its executable details. The trusted adapter maps that role to:

- cached image `postgres:17-alpine` with exact local image content digest
  `742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`;
- no model-controlled argv;
- the existing release-owned
  `integration.postgres.pg-isready.v1` health recipe;
- a 256 MiB ephemeral tmpfs data volume, 512 MiB memory ceiling, bounded CPU,
  and 64-process ceiling;
- one and only one opaque password secret reference;
- the stable consumer identity `integration:postgresql`, independent of the
  candidate/post-apply phase or candidate-selected logical service ID; and
- no host-published port while the Docker network is internal.

The secret provider must materialize the referenced value under tool key
`POSTGRES_PASSWORD`; the Docker adapter exposes only
`POSTGRES_PASSWORD_FILE` and removes its mode-0600 source immediately after
launch. Console and Shell show the 256 MiB ephemeral-storage ceiling together
with the network ceiling, secret reference, consumer, tool-key convention, and
grant digest before the separate resource approval.

Core re-derives the complete supplemental `EngineeringResourceImpact`, not
only its network bytes. A widened process, command, storage, or network budget
therefore fails before launch. If both an API and PostgreSQL role consume
secrets, every reference must be explicitly scoped in the owner words as an
API or PostgreSQL secret. One reference cannot be assigned to two roles.

Natural SQLite planning no longer claims requests that explicitly name
PostgreSQL or MySQL. This prevents the candidate-only SQLite adapter from
failing a legitimate remote-engine service request before integration
composition runs.

The existing phase-qualified service IDs remain in environment plans and
receipts. Secret adapters derive stable consumers only after matching the
trusted fixed recipe or image identity; all other plans retain the
deterministic logical-ID fallback. No new consumer field enters candidate data
or the public integration-service contract.

## Consequences

- A natural request can start, health-check, evidence-bind, repeat after apply,
  and clean a real PostgreSQL container through the same Core integration
  lifecycle and separate secret grant.
- The model cannot select an image, image digest, command, health recipe,
  secret value, budget, or port.
- Candidate and post-apply runs can use one separately provisioned secret
  because their consumer identity is stable.
- A PostgreSQL-only graph consumes no pre-reserved host port, eliminating a
  port-release race for this template.
- This does not create a remote `DatabaseTarget`, run SQL migrations, expose a
  database endpoint, persist database data, or mutate production.

## Failed experiment retained

Docker accepted both dynamically and explicitly requested loopback publication
metadata on an `--internal` network, but `docker port` returned no published
binding and `.NetworkSettings.Ports` remained null. The diagnostic containers
and networks were removed. The template therefore has no host port; later
remote-database attachment must use an enforceable broker-backed design rather
than disabling isolation.

## Alternatives considered

- Let `fam.integration.json` name an image, argv, or environment variables:
  rejected because candidate/model data is untrusted.
- Use `POSTGRES_HOST_AUTH_METHOD=trust`: rejected because it removes the
  explicit opaque-secret boundary.
- Publish a host port despite the internal-network result: rejected because the
  observed daemon did not provide the claimed endpoint and weakening the
  network was out of scope.
- Call service health “PostgreSQL database migration support”: rejected because
  no SQL plan, backup, transaction, restore, or schema/data receipt exists yet.

## Evidence

- `src/fam_os/core/engineering/natural_integration_declaration.py`
- `src/fam_os/core/engineering/natural_integration_resources.py`
- `src/fam_os/core/engineering/integration_environment.py`
- `src/fam_os/adapters/integration/postgresql_template.py`
- `src/fam_os/adapters/integration/natural_template_identity.py`
- `src/fam_os/adapters/integration/natural_template_selection.py`
- `src/fam_os/adapters/integration/natural_resource_planning.py`
- `src/fam_os/adapters/integration/natural_planning.py`
- `src/fam_os/adapters/integration/secret_consumer.py`
- `tests/unit/test_natural_integration_environment.py`
- `tests/integration/test_natural_postgresql_environment.py`
