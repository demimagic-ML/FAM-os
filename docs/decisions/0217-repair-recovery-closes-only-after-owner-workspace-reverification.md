# ADR 0217: Repair recovery closes only after owner-workspace reverification

Status: Accepted

## Context

The bounded repair path recorded two ordered recovery observations immediately
from one candidate verification set, then reported and closed the incident
before the owner approved or received the changeset. Although the receipts were
ordered, the second record was not an independently later observation of the
repaired result and could not prove recovery survived application to the owner
workspace.

## Decision

Candidate repair verification records exactly one recovery observation and
leaves the incident in `recovery_monitored`. The incident remains visible and
open while the exact repaired changeset waits for owner approval.

After approval and transactional apply, the ordinary signed post-apply verifier
runs against the owner workspace. Only a wholly passing post-apply set may
record the second recovery observation. Its source is the first observation
receipt and its conclusion binds the distinct post-apply verification IDs.
Only then may Core create the post-incident report and closure receipts.

The operation remains restart-safe. A retry with one observation adds the
second; a retry with two observations continues reporting or closure without a
third observation. A failed post-apply verification does not close recovery
and instead follows the exact rollback incident branch.

## Consequences

- `recovery_monitored` truthfully means one successful candidate observation
  has occurred and later owner-workspace confirmation is still pending.
- Incident closure proves both repaired-candidate verification and independent
  post-apply reverification.
- The changeset checkpoint can display an open monitored incident without
  representing the repair as failed.
- Existing rollback/report/closure behavior is unchanged.
- Signed installed and live proof are still required before Phase 30.7 is
  complete.

## Alternatives considered

- Keep two immediate receipts from the same verification set. Rejected because
  sequence alone is not independent later observation.
- Close on candidate verification and reopen after apply failure. Rejected
  because it transiently overstates recovery and complicates durable truth.
- Run an arbitrary timer probe before approval. Rejected because elapsed time
  without observing the applied owner result provides weaker evidence than the
  existing signed post-apply verifier.

## Evidence

- `src/fam_os/product/natural_engineering_incidents.py`
- `src/fam_os/product/natural_engineering_repair.py`
- `src/fam_os/product/natural_engineering_api.py`
- `tests/integration/test_natural_engineering_incident.py`

## Superseded decisions

None. This narrows the recovery interpretation in ADR 0214 without changing its
bounded repair or final-state changeset decisions.
