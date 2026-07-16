# Authenticated Local Application Transport

## Purpose

Phase 5.2 provides the private, bounded transport between FAM Core-side
Application Fabric coordination and local connector processes. It transports
typed connector registration, scoped observation requests/results, prepared
and confirmed actions, connector events, cancellation, acknowledgements, and
safe errors. It does not grant application permission and it carries no raw
model or MCP session.

## Endpoint and authentication

- The server listens on an absolute Unix-domain socket below a real directory
  owned by the current user and not writable by group or world.
- It refuses to replace an existing path and creates the socket with mode
  `0600`.
- Linux `SO_PEERCRED` binds each accepted stream to its kernel-reported PID,
  UID, and GID before any message is accepted.
- The initial policy admits only the configured local UID and, optionally, a
  configured primary GID set.
- The first valid message is a typed `ConnectorRegistration`; its connector ID
  becomes immutable for the session.

This is authenticated user-session IPC, not connector-package attestation. A
different process already running as the same Unix user is inside this phase's
trust boundary. Package signatures, launch capabilities, sandboxing, and
process provenance remain separate hardening layers.

## Framing and envelope

Each message is canonical UTF-8 JSON preceded by a four-byte network-order
length. Empty frames and frames above 1 MiB are rejected before decoding. The
envelope has exactly five fields:

```text
contract_version, message_id, kind, correlation_id, payload
```

The transport version is `fam.applications.local/v1alpha1`. Typed payloads are
self-describing `fam.applications/v1alpha1` schema documents encoded and
decoded through the shared strict schema registry. Unknown envelope fields,
unknown kinds, unsupported versions, malformed UTF-8/JSON, and wrong contract
types fail closed.

## Direction and correlation

| Core to connector | Required connector result |
|---|---|
| `observe` with `ObservationRequest` | `observation` with `ObservationResult` |
| `prepare_action` with `ActionPreparationRequest` | `action_proposal` with `ActionProposal` |
| `confirm_action` with `ActionConfirmation` | `action_result` with `ActionResult` |

Every result carries the original message ID as `correlation_id`. A session
records both the pending ID and expected result family. Unknown, replayed, or
wrong-family results reject without consuming the pending request. A typed
decode or consumer failure also leaves the request pending so a valid response
can still arrive.

Connectors may initiate only registration, connector events, cancellation,
typed results, and safe errors. They cannot initiate Core observation or action
requests. The transport does not expose user intent as unrestricted prose;
connectors receive only admitted, permission-scoped request contracts.

## Live Core request broker

Phase 5.12 adds `ConnectorRequestBroker` above the authenticated connection and
registry dispatcher. The endpoint reports each accepted connection to the
broker; after typed registration, Core can issue correlated observation,
preparation, and confirmation requests by connector ID. The broker waits on a
bounded condition, rejects unavailable connectors, maps transport errors to
content-free failures, and removes connection ownership on disconnect.

This closes the production outbound-composition seam used by the real VS Code
acceptance. It does not alter direction policy, grant authority, or make a
connector result trusted verification.

## Cancellation and disconnect

Either side can identify pending work with a `cancel` message. Core uses a
dedicated cancellation operation that retires the original pending request
without creating another pending operation. A connection close atomically
removes its connector registration and reports each remaining request to the
consumer as `transport.disconnected` without exposing connector exception text.

`INSTANCE_CLOSED` also removes the registration. Other connector events are
acknowledged as refresh signals; changed capabilities become authoritative only
through a new atomic registration.

## Permission and policy boundary

Transport authentication means only that an admitted local peer can exchange
messages. Capability registration does not grant observe, propose, modify, or
execute authority. Core remains responsible for permission scope, confirmation,
expiry, verification, final-result policy, and audit. Payloads and connector
claims remain untrusted input.

MCP can later be normalized by an adapter onto these Application Fabric
contracts, but no MCP object, SDK, server session, or model handle enters this
transport implementation.

## Evidence

- `tests/unit/test_local_application_transport.py`
- `tests/unit/test_local_application_contract_transport.py`
- `tests/architecture/test_local_transport_boundary.py`
- ADR 0040
