# ADR 0184: Docker integration is digest-pinned, internal, and file-secret-injected

Status: Accepted

## Context

Phase 27.13 needs a concrete container environment without giving Core or a
model raw Docker access. Docker image tags can move, normal bridge networks
permit egress, bind volumes lack enforceable size quotas, environment-variable
secrets persist in daemon metadata, and a crash can strand containers or
networks.

## Decision

The Docker adapter invokes one immutable root-owned `/usr/bin/docker` through a
no-shell, output-bounded, deadline-bounded client with a sanitized environment.
It verifies the local image content ID equals the plan SHA-256 before launch and
uses `--pull never`.

Each environment gets a labeled `--internal` network. Containers are read-only,
no-new-privileges, capability-dropped with only the bounded compatibility set,
PID-, memory-, CPU-, and tmpfs-limited, and uniquely named from environment plus
service identity. Writable declared volumes are size-bounded tmpfs mounts.
Read-only candidate inputs are symlink-rejected and measured before bind mount.
Retained writable volumes and external allowlisted egress fail closed until an
enforceable implementation exists.

Opaque secrets enter only the adapter. They are written to owner-private
mode-0600 ephemeral files, bind-mounted read-only, and represented inside the
container only as `KEY_FILE=/run/fam-secrets/KEY`. The host pathname is removed
immediately after container creation. Secret plaintext is absent from argv,
the Docker client environment, receipts, and daemon `.Config.Env` metadata.

Before effects the adapter exclusively claims a candidate-local state file.
Network and container runtime identities are durably recorded as they are
created. Any launch, health, cancellation, or revocation failure removes
recorded partial resources. Restart reconciliation reads only those exact
identities, removes them without requiring renewed mutation authority, records
cleanup evidence, and cannot replay a cleaned state.

Health is either a bounded loopback TCP probe or an independently trusted signed
recipe runner. The PostgreSQL qualification uses exact `pg_isready` argv over
`docker exec`; no shell is involved.

## Consequences

- Cached tag substitution and network egress fail closed.
- Docker metadata does not become a plaintext secret store.
- A writable volume cannot exceed its tmpfs bound, but retained-volume export
  is unavailable until bounded extraction exists.
- Docker's internal network cannot publish a loopback host port; plans needing
  such a port currently fail during port inspection and are cleaned. A future
  supervised loopback proxy or enforceable network backend requires a new ADR.
- Process, browser, HTTP-health, cluster, product composition, and installed
  qualification remain open.

## Evidence

- `src/fam_os/adapters/integration/docker_client.py`
- `src/fam_os/adapters/integration/docker_environment.py`
- `src/fam_os/adapters/integration/docker_service.py`
- `src/fam_os/adapters/integration/docker_state.py`
- `tests/unit/test_docker_integration_environment.py`
- `tests/integration/test_docker_integration_environment.py`
