# ADR 0185: Integration environments persist encrypted and reconcile without relaunch

Status: Accepted

## Context

The Docker adapter records runtime identities inside the candidate, but that is
not enough for an installed product to discover owner environments, preserve
the Core-issued permit required for cleanup, or recover after Core restarts.
Automatically relaunching a service would repeat effects under an expired or
revoked authority. Persisting plans or secret references as plaintext would
also turn product state into an unnecessary disclosure surface.

## Decision

Core start returns an `IntegrationEnvironmentStartResult` containing the exact
five-minute permit, the canonical SHA-256 of the admitted plan, and the launch
receipt. The product stores the plan, candidate, start result, and latest
receipt as owner-context AEAD ciphertext. Plaintext indexes contain only owner,
task, candidate, plan digest, lifecycle state, and timestamps. Start and cleanup
receipts are also retained as an append-only encrypted event stream.

Lifecycle state is `active`, `failed`, or terminal `cleaned`. An environment ID
is single-use. Cleanup and restart reconciliation require the original plan,
candidate, permit, and receipt identities. Cleanup remains possible after
authority expiry or revocation because it can only reduce resources. It mints a
fresh receipt ID, and a terminal environment is rejected before an adapter
effect.

Product startup never relaunches an active environment. When the trusted Docker
adapter is available, it removes only candidate-recorded runtime identities and
atomically records the reconciliation receipt. A failed reconciliation remains
active and is reported as an unresolved recovery outcome. When Docker is
unavailable, encrypted state remains intact for later recovery.

The owner can start, list, inspect, audit, clean, or reconcile through either
the authenticated loopback Console or the owner-UID mode-0600 Unix Shell.
Console mutations use the existing session, Origin, CSRF, exact-field, and
confirmation boundary. Shell uses four strict versioned request/response roots.
Start still requires Core to derive live `EXECUTE`, per-host `NETWORK`, and
per-reference `SECRET_USE` decisions from the owner grant; neither surface can
mint a permit itself.

If launch succeeds but durable insertion fails, the product immediately invokes
exact cleanup compensation. If both persistence and compensation fail, it
reports that compound failure rather than claiming a safe start.

## Consequences

- Restart does not repeat launch effects or silently extend authority.
- Cleanup evidence and current state cannot diverge through receipt-ID replay.
- Console and Shell expose lifecycle control without exposing Docker or raw
  repository primitives.
- A host without the trusted Docker adapter cannot reconcile until that adapter
  becomes available; it does not discard the active encrypted record.
- Process, API, browser, retained-artifact, allowlisted-egress, and local-cluster
  adapters remain separate Phase 27.13 work.

## Evidence

- `src/fam_os/product/storage/migrations/0030_integration_environments.sql`
- `src/fam_os/product/storage/integration_environment_repository.py`
- `src/fam_os/product/integration_environment_api.py`
- `src/fam_os/console/integration_environment_routes.py`
- `src/fam_os/shell/integration_environment_contracts.py`
- `tests/unit/test_integration_environment_repository.py`
- `tests/unit/test_product_integration_environment_api.py`
- `tests/integration/test_console_integration_environments.py`
- `tests/unit/test_fam_shell_integration_environment_transport.py`
