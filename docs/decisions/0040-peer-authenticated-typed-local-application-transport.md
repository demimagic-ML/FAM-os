# ADR 0040: Use peer-authenticated typed Unix transport for local connectors

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Use a private `0600` Unix-domain socket, Linux `SO_PEERCRED`, bounded canonical
JSON framing, strict versioned Application Fabric documents, immutable
connector/session binding, and request-ID plus expected-result-family
correlation for the initial local connector transport.

Keep framing, peer authorization, session state, typed codec, dispatch,
registry coordination, connection lifecycle, and listener ownership in small
separate modules. Core sends only observation, action-preparation, and
confirmation requests. Connector registration, events, typed results, safe
errors, and cancellation are the only connector-initiated message families.

Treat this as current-user session authentication. It does not attest a
connector package or protect against a different process already running as
that Unix user. Permission, confirmation, verification, and audit remain Core
policy and cannot be inferred from transport admission.

## Consequences

- Kernel-reported peer identity replaces caller-supplied UID/PID claims.
- Oversized, malformed, incompatible, replayed, and wrong-family messages fail
  before they can satisfy pending work.
- Disconnect deterministically unregisters capabilities and yields safe errors
  for unfinished operations.
- MCP and native connector implementations can share provider-neutral contracts
  without becoming the internal protocol.
- Future package attestation, one-time launch capabilities, persistent endpoint
  supervision, and multi-user isolation require later decisions.

## Evidence

- `src/fam_os/applications/transport/`
- `tests/unit/test_local_application_transport.py`
- `tests/unit/test_local_application_contract_transport.py`
- `tests/architecture/test_local_transport_boundary.py`
- `docs/protocols/AUTHENTICATED_LOCAL_APPLICATION_TRANSPORT.md`
