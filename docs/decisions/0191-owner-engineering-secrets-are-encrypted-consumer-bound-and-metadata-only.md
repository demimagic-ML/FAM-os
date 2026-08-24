# ADR 0191: Owner engineering secrets are encrypted, consumer-bound, and metadata-only

Status: Accepted

Supersedes: the product-default-deny limitation in ADR 0190. ADR 0190's
process-file lifetime and cleanup rules remain accepted.

## Context

ADR 0190 provided installed file-injection mechanics but product composition
still denied all references because no owner-controlled provider existed. A
test provider is not sufficient for owner sovereignty, and a generic plaintext
settings file would bypass authentication, encryption, consumer binding,
rotation history, and Console/Shell visibility.

## Decision

Migration 0031 adds owner-scoped engineering secret records and append-only
metadata audit events. Each active record binds an opaque `secret.*` reference
to one uppercase tool key, one exact consumer ID, and one generation. Values
are AES-256-GCM encrypted under the existing owner master key with associated
data binding owner, record type, reference, and generation. Rotation writes a
new generation; deletion tombstones metadata and removes the live ciphertext.

Only the concrete integration provider can resolve active plaintext. Core,
receipts, audit events, list, inspect, Console responses, and Shell responses
receive metadata only. Multiple requested references with the same tool key or
a mismatched consumer fail before adapter materialization.

Provision, rotation, and deletion each require a confirmed, two-minute,
single-use owner authentication context over the exact operation digest. The
context is transport-session-bound. Validation and consumption are atomic:
wrong sessions or digests do not burn a legitimate context. Console applies
its normal loopback session, Origin, and CSRF controls. Shell uses strict
versioned request/response roots over the owner-UID mode-0600 Unix socket.

The product composes this repository directly as the optional provider for
Docker and process backends. No plaintext passes through Core. Restart retains
encrypted references but never replays a mutation context.

## Consequences

- The owner can provision, inspect metadata, rotate, delete, and audit exact
  integration credentials through both local product surfaces.
- An installed owner-to-Core-to-real-process test proves the complete opaque
  path and restart cleanup.
- Secret values are necessarily present in confirmed local mutation requests
  and short-lived mode-0600 adapter files; they never appear in responses.
- Rotating or deleting a reference prevents future materialization but does not
  forcibly remove a file already mounted into a running environment. Immediate
  active-use revocation requires an environment-to-reference index and exact
  cleanup coordination.
- Secure external secret-store adapters and disclosure/rotation providers may
  replace repository resolution without changing Core contracts.

## Evidence

- `src/fam_os/product/storage/migrations/0031_engineering_secrets.sql`
- `src/fam_os/product/storage/engineering_secret_repository.py`
- `src/fam_os/product/engineering_secret_api.py`
- `src/fam_os/console/engineering_secret_routes.py`
- `src/fam_os/shell/engineering_secret_contracts.py`
- `src/fam_os/adapters/shell/engineering_secret_dispatch.py`
- `tests/integration/test_installed_process_owner_restart_chain.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt8.json`
