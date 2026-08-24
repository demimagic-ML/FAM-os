# ADR 0199: Engineering governance is receipt-bound and restart-safe

Status: Accepted

## Context

Generated documentation, independent review, and incident response can become
ceremonial labels unless their inputs, findings, transitions, and exceptions are
durable and machine-checkable.

## Decision

Generated diagrams, API references, runbooks, changelogs, and generated code use
candidate-bound requests. Receipts bind the exact signed generator recipe,
sources, output digest, ownership path, and authoritative regeneration
instructions. Staleness is a deterministic comparison of source and output
digests. Requirement traces cannot claim satisfaction without implementation,
test, and evidence references.

Code, security, architecture, and design review share one independent checkpoint
contract. The producer cannot be the reviewer. Findings are typed, attributable,
and persisted with optimistic revisions. Open findings block passage. Resolution
requires a receipt. Waiver requires a typed owner decision over an exact
consequence digest and truthfully reduces assurance.

Engineering incidents use an append-only, hash-chained state machine persisted
with optimistic revisions. Evidence preservation must precede diagnosis;
remediation is proposed before application; recovery must be monitored or rolled
back; and reporting precedes closure.

## Consequences

- Generated output drift is detectable without model judgment.
- Review findings survive restart and cannot disappear through a stale write.
- A waiver cannot be represented as a passed review.
- Incident chronology and evidence are explicit and auditable.
- Phase 30.6--30.8 remain open until these services are product-composed and
  exercised through the master engineering lifecycle.

## Evidence

- `src/fam_os/core/engineering/documentation.py`
- `src/fam_os/core/engineering/documentation_service.py`
- `src/fam_os/core/engineering/review.py`
- `src/fam_os/core/engineering/review_service.py`
- `src/fam_os/core/engineering/incident.py`
- `src/fam_os/adapters/sqlite/engineering_review.py`
- `src/fam_os/adapters/sqlite/engineering_incident.py`
- `tests/unit/test_governed_documentation.py`
- `tests/unit/test_engineering_review_service.py`
- `tests/unit/test_engineering_incident_service.py`

## Superseded decisions

None.
