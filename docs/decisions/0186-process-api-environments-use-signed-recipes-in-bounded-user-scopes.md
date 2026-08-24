# ADR 0186: Process and API environments use signed recipes in bounded user scopes

Status: Accepted

## Context

Phase 27.13 also requires real processes and APIs. Giving a plan arbitrary argv
would recreate raw shell. A plain subprocess cannot enforce memory, task, CPU,
or network policy, and a transient systemd service on the qualification host
cannot create the Bubblewrap user namespace needed for filesystem isolation.
The same Bubblewrap command does work when the owner process joins a transient
user scope.

## Decision

Process and API services reference an exact `recipe-id@version`. The adapter
resolves it through `SignedToolRecipeCatalog` and requires the plan argv to equal
the signed recipe argv exactly. The resolved executable must be a regular,
root-owned, non-group/world-writable file. No shell or model-generated command
is accepted.

The adapter launches `/usr/bin/bwrap` through `/usr/bin/systemd-run --user
--scope`. Bubblewrap removes capabilities and environment, creates user, PID,
IPC, UTS, and cgroup namespaces, exposes only immutable runtime trees plus the
exact candidate at `/workspace`, and provides fresh `/tmp`, `/proc`, and `/dev`.
The systemd scope enforces `MemoryMax`, `MemorySwapMax=0`, `TasksMax`, CPU quota,
and a three-second stop deadline.

Network-denied scopes set `IPAddressDeny=any`. Isolated loopback APIs add only
`IPAddressAllow=localhost`. Allowlisted egress fails closed until a resolver and
address-churn-safe policy backend exist. Host ports must be allocated before
admission and bind loopback by contract.

Candidate-local state durably records exact scope names before health
acceptance. TCP, HTTP, and active-scope health are bounded and recheck live
authority between attempts. Cleanup sends bounded TERM then KILL to only the
recorded scopes, requests nonblocking unit retirement, verifies inactivity,
and records a fresh receipt. Restart reconciliation uses the same exact state
without relaunch or renewed mutation authority.

A provider-neutral executor router selects a homogeneous Docker or process/API
backend. Mixed-backend graphs fail closed until a higher-level orchestrator can
coordinate partial startup and reverse-order compensation across providers.

## Consequences

- A signed service recipe cannot be widened with extra plan arguments.
- Real loopback HTTP APIs run with measured cgroup limits and no external IP
  access under the systemd policy.
- Secret injection, declared volumes, retained artifacts, dynamic port zero,
  and allowlisted egress currently fail closed for this backend.
- Product composition accepts a process backend only when a trusted signed
  recipe catalog is supplied; no unsigned default recipe is synthesized.
- Browser and mixed local-cluster orchestration remain open.

## Failed experiments retained

- A transient user service with one task failed before Bubblewrap could fork.
  The fixture budget was corrected to 16 tasks.
- A transient user service with sufficient tasks still failed its UID map on
  this host. A bounded user scope passed the identical Bubblewrap isolation.
- `systemctl stop` could wait for the default 90-second scope timeout after the
  task exited. Cleanup now uses bounded exact-scope TERM/KILL plus nonblocking
  stop and configures a three-second transient timeout.

## Evidence

- `src/fam_os/adapters/integration/process_environment.py`
- `src/fam_os/adapters/integration/process_client.py`
- `src/fam_os/adapters/integration/process_state.py`
- `src/fam_os/adapters/integration/environment_router.py`
- `tests/unit/test_process_integration_environment.py`
- `tests/integration/test_process_api_integration_environment.py`
- `tests/unit/test_integration_environment_router.py`
