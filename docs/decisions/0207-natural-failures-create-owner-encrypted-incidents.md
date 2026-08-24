# ADR 0207: Natural failures create owner-encrypted incidents

Status: Accepted

## Context

The incident state machine from ADR 0199 was component-tested but disconnected
from the natural engineering path. A generation, edit, candidate-verification,
changeset-preview, or post-apply verification failure could therefore be shown
to an owner without durable incident identity, restart reconstruction, or an
evidence-preserving route to diagnosis and remediation. Product composition
would also have persisted the component store's serialized incident document in
plaintext.

## Decision

Natural engineering failures create exactly one deterministic incident from the
task identifier, failure code, and concrete evidence identifiers already
produced by generation, editing, verification, or changeset services. Detection
does not claim diagnosis. Later stages continue to use the ordered state machine
from ADR 0199 and each transition requires a non-empty evidence identifier.

The unprivileged product composition owns the incident service. Incident
documents use owner-bound AEAD in product storage, retain only indexed task and
revision metadata outside ciphertext, and migrate the former strict serialized
record only when it is unambiguously the prior plaintext format.

Console and Shell expose typed incident listing and separately confirmed,
evidence-bound advancement. Neither transport accepts a caller-supplied
incident document or skips a state-machine transition.

## Consequences

- A failed natural task remains inspectable after restart with the exact
  generation, edit, verification, or changeset identifier that detected it.
- The system cannot represent detection as diagnosis or remediation without a
  later evidence-bearing transition.
- Owner-visible transports operate on Core state rather than free-form model
  claims.
- Incident contents are not plaintext durable product state.
- Phase 30.7 remains open until evidence preservation, diagnosis, remediation,
  recovery monitoring, rollback, reporting, and closure are automatically
  orchestrated and proved from the signed installed product.

## Alternatives considered

- Attach an ephemeral error object to the response. Rejected because restart
  would erase chronology and recovery state.
- Let the model emit the diagnosis and remediation stages directly. Rejected
  because model text is not a trusted receipt.
- Store component JSON unchanged after product composition. Rejected because it
  conflicts with the established owner-encrypted product-state boundary.

## Evidence

- `src/fam_os/product/engineering_incident_api.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/product/natural_engineering_api.py`
- `src/fam_os/product/composition/engineering_loop.py`
- `src/fam_os/adapters/sqlite/engineering_incident.py`
- `src/fam_os/console/engineering_loop_routes.py`
- `src/fam_os/shell/engineering_loop_contracts.py`
- `src/fam_os/shell/engineering_candidate_contracts.py`
- `tests/integration/test_natural_engineering_incident.py`
- `tests/integration/test_console_engineering_loop.py`
- `tests/unit/test_fam_shell_engineering_loop_transport.py`
- `tests/unit/test_engineering_incident_service.py`

## Superseded decisions

None. This composes and narrows the operational consequences of ADR 0199.
