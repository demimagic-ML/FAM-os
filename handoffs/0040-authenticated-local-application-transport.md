# Handoff 0040: Authenticated local Application Fabric transport

**Date:** 2026-07-16  
**Plan step:** Phase 5.2  
**Status:** Complete  
**Previous handoff:** `0039-application-capability-registry.md`

## Objective

Implement the private local transport that carries strict Application Fabric
registration, observation, action, event, cancellation, and result contracts
without exposing provider sessions or bypassing Core policy.

## Scope completed

- Private `0600` Unix endpoint with safe path ownership and non-replacement.
- Kernel `SO_PEERCRED` PID/UID/GID extraction and configurable user/group policy.
- Canonical length-prefixed UTF-8 JSON with a 1 MiB maximum and strict envelope.
- Typed shared-schema codec for connector and application contract documents.
- Immutable connector/session binding and atomic registry registration/removal.
- Request correlation bound to the expected response family.
- Bidirectional cancellation, safe disconnect failures, and registry cleanup.
- Typed observation, proposal, and action-result integration tests.

## Explicitly not completed

- Connector-package attestation or protection from another process under the
  already-authorized Unix user.
- Persistent multi-connection accept loop, launch supervision, or multi-user IPC.
- MCP, VS Code, D-Bus, accessibility, and screen/input adapters.

## Architecture and decisions

ADR 0040 selects peer-authenticated Unix IPC and preserves the Application
Fabric contracts as the wire payload authority. Transport admission authenticates
the current user session only; permission, confirmation, verification, and audit
remain Core responsibilities. Expected result families are stored with pending
IDs so correlation cannot cross observation and action boundaries.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/transport/` | Wire, framing, auth, session, codec, dispatch, connection, endpoint, and ports. |
| `tests/unit/test_local_application_transport.py` | Framing, peer auth, session, endpoint, and connection tests. |
| `tests/unit/test_local_application_contract_transport.py` | Typed registry/request/result/cancel/disconnect tests. |
| `tests/architecture/test_local_transport_boundary.py` | Provider/Core policy import guard. |
| `docs/protocols/AUTHENTICATED_LOCAL_APPLICATION_TRANSPORT.md` | Protocol and security boundary. |
| `docs/decisions/0040-peer-authenticated-typed-local-application-transport.md` | Durable transport decision. |
| `README.md`, `src/fam_os/applications/README.md`, `MASTER_PLAN.md` | Ownership and status. |

## Public interfaces

- `LocalMessage`, `LocalMessageKind`, and `LOCAL_TRANSPORT_VERSION`.
- `contract_message`, `decode_contract_message`, bounded frame functions.
- `UnixPeerCredentials`, `PeerAuthorizationPolicy`, `LocalTransportSession`.
- `AuthenticatedLocalConnection.send_request()` and `.cancel_request()`.
- `RegistryMessageDispatcher` and `ApplicationMessageConsumer`.
- `UnixEndpointConfiguration` and `UnixApplicationServer`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_local_application_transport tests.unit.test_local_application_contract_transport tests.architecture.test_local_transport_boundary
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: 15 focused and 427 total tests passed; all 35 schema artifacts matched;
compile and AST size gates passed. Larry indexed 571 files / 1,613 symbols; its
graph has 7,885 nodes / 27,298 edges and clean health. The persisted code graph
was refreshed in fast mode with the same node and edge totals.

## Evidence and artifacts

- `docs/protocols/AUTHENTICATED_LOCAL_APPLICATION_TRANSPORT.md`
- `docs/decisions/0040-peer-authenticated-typed-local-application-transport.md`
- Focused live Unix socket tests in the two transport test modules.

## Known limitations and risks

- Same-UID processes share the current authentication boundary; package
  provenance and one-time launch capabilities need later hardening.
- Registry and session state remain process-local and reconnect starts a new
  session.
- The endpoint serves one connection per `serve_once` invocation; deployment
  supervision and concurrency belong to a later service composition step.

## Operational notes

Tests create only temporary Unix sockets and socket pairs. All endpoints are
closed and removed; no persistent services, models, ports, or credentials are
used.

## Recommended next entry point

Begin Phase 5.3. Read `docs/architecture/MCP_APPLICATION_CONNECTOR.md`, ADR 0012,
and the transport/registry public APIs. Implement an MCP client behind a small
provider port and normalize only approved local resources/tools into capability
registrations; do not import MCP types into Application Fabric contracts.
