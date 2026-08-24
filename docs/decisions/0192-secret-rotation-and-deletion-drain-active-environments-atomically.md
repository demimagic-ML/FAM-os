# ADR 0192: Secret rotation and deletion drain active environments atomically

Status: Accepted

Extends: ADR 0191. ADR 0190 remains authoritative for process-file lifetime.

## Context

ADR 0191 made future materialization observe the latest encrypted generation,
but a process that had already received a secret file could continue using the
old value after owner-authorized rotation or deletion. A scan followed by a
mutation without serialization would also race an environment start: the scan
could observe no active record while the start was still materializing the old
generation.

## Decision

One product-level re-entrant lifecycle coordinator serializes integration
environment start, cleanup, and reconciliation with engineering secret
rotation and deletion. Start holds the coordinator from before provider
resolution through durable active-state persistence. Rotation and deletion
consume their exact single-use owner authentication context, then hold the same
coordinator while they inspect persisted active environments, clean every plan
whose immutable service declarations contain the exact reference, validate and
persist cleanup evidence, and finally commit the encrypted secret mutation.

An unrelated environment is not stopped. If any matching cleanup fails, the
secret mutation is not committed. Cleanup already completed before a later
failure remains truthfully terminal and the consumed authentication context is
not reusable. A new context is required to retry the remaining work.

Lifecycle coordination is mandatory for `ProductEngineeringSecretApi`; there
is no uncoordinated construction mode. If a concrete environment adapter is
unavailable, a persistence-backed fail-closed facade still exposes active
records. It refuses their cleanup, so a matching rotation or deletion cannot
silently advance while active use may remain.

## Consequences

- An owner-authorized rotation or deletion is immediate revocation for every
  product-managed active environment using that exact reference.
- A concurrent start either completes and is then drained before mutation, or
  starts afterward and observes the new generation or deleted state.
- Cleanup receipts remain the durable evidence; no secret content enters the
  environment index, receipt, Console response, Shell response, or audit event.
- The coordinator is process-local. Product active-state persistence and
  single-owner service composition remain the cross-restart source of truth.
- Same-UID host trust, external secret brokers, portable browser packaging,
  mixed-backend clusters, and allowlisted egress are unchanged.

## Alternatives considered

- Rotate first and asynchronously stop environments: rejected because old
  material remains usable after a successful owner response.
- Maintain a second mutable reference index: rejected for now because the
  immutable encrypted plans already provide exact durable membership and the
  expected active set is bounded.
- Treat adapter unavailability as no active use: rejected because persisted
  active records must fail closed.

## Evidence

- `src/fam_os/product/engineering_secret_lifecycle.py`
- `src/fam_os/product/engineering_secret_api.py`
- `src/fam_os/product/integration_environment_api.py`
- `tests/unit/test_engineering_secret_api.py`
- `tests/unit/test_product_integration_environment_api.py`
- `tests/integration/test_installed_process_owner_restart_chain.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt10.json`
