# ADR 0212: Incident transitions require stored typed evidence

Status: Accepted

## Context

ADR 0207 attached deterministic incidents to natural engineering failures, but
the product-facing advance operation still accepted an arbitrary stage and
evidence identifier. The component state machine checked transition order, yet
it could not prove that the named evidence existed, belonged to the incident,
or represented the requested transition. Detection also stopped before the
automatic evidence-preservation and diagnosis work promised by Phase 30.7.

## Decision

Every engineering-incident transition exposed by the product is backed by an
immutable `EngineeringIncidentEvidenceReceipt`. The receipt binds the incident,
task, typed evidence kind, prior evidence identifiers, conclusion code,
timestamp, contract version, and canonical payload digest. The owner-private
SQLite adapter stores receipts separately from states, rejects identity reuse,
and migrates earlier plaintext state and receipt rows through the existing
owner-bound codec.

Natural generation, candidate-edit, verification, checkpoint, and post-apply
failures now detect one deterministic incident and automatically create the
preservation and diagnosis receipts in order. The receipt is durably stored
before its state transition. Retries reconstruct the same incident and receipts
without duplicating evidence. Console and Shell expose the resulting evidence
read-only alongside incident state.

A client may no longer advance an incident using a claimed identifier. The
compatibility operation accepts only a receipt already present in the trusted
store, and its kind must map exactly to the requested next stage. New evidence
can be recorded only through the internal product boundary that receives real
remediation, recovery, rollback, reporting, or closure outcomes.

## Consequences

- Fabricated, cross-incident, and wrong-stage evidence cannot move product
  incident state.
- Failure return paths preserve evidence and diagnosis before presenting the
  terminal failure to the owner.
- Restart preserves both the incident chain and the evidence needed to explain
  it without retaining model prompts, source content, or secret values.
- Phase 30.7 remains open: real remediation, monitored recovery, rollback,
  post-incident report, closure orchestration, and signed-installed execution
  still have to be connected to their producing outcomes.

## Alternatives considered

- Keep arbitrary stage advancement and trust callers. Rejected because an
  identifier is not proof of an observed result.
- Store receipts only inside the state document. Rejected because independent
  immutable receipt lookup is required for exact transition validation and
  restart reconciliation.
- Automatically mark every detected failure closed. Rejected because closure
  without remediation, recovery or rollback, and a report would be false.

## Evidence

- `src/fam_os/core/engineering/incident.py`
- `src/fam_os/adapters/sqlite/engineering_incident.py`
- `src/fam_os/product/engineering_incident_api.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/product/natural_engineering_api.py`
- `tests/unit/test_engineering_incident_service.py`
- `tests/integration/test_natural_engineering_incident.py`

## Superseded decisions

This narrows the product transition surface introduced by ADR 0207. It does not
supersede the deterministic incident identity or owner-encrypted persistence
chosen there.
