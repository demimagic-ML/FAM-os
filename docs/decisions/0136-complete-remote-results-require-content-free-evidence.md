# ADR 0136: Complete remote results require content-free evidence

**Status:** Accepted  
**Date:** 2026-07-17  
**Extends:** ADR 0135

## Context

Authenticating a complete mutual-TLS response before constructing a candidate is
necessary but insufficient for durable audit and final release. Without one
record joining route, disclosure, signed result, budget, candidate, and verifier
identities, later policy cannot prove that the released candidate is the exact
complete peer result. Conversely, persisting response fragments for recovery
would retain untrusted content and create an accidental partial candidate.

## Decision

Every authenticated complete remote result creates exactly one
`RemoteExecutionEvidence` in the requester product database. The record is
encrypted and content-free. It binds the Core instance and request, canonical
remote-plan digest, canonical execution request and peer-signed result digests,
enrollment, peer device, expert, model, expert tier, signed capability
declaration, exact context evidence and receipt, global budget reservation and
attempt, candidate and result content digests and byte counts, and authentication
time.

Candidate evidence and the initial `authenticated_candidate` remote record are
inserted in one transaction. Verification may finalize the record once as
`released`, `rejected`, or `withheld`. A verified acceptance and the matching
remote finalization commit in one transaction. Final-result policy requires the
terminal plan event to reference this record and rechecks its request, candidate,
disposition, verification outcome, and acceptance evidence before releasing
content.

Raw result content and response fragments are not legal evidence fields.
Truncated, timed-out, unsigned, identity-mismatched, or receipt-mismatched
responses create neither a candidate nor a remote-execution evidence record.
Rejected complete results retain only content-free audit evidence and may enter
the already bounded local repair path through a new candidate.

The authenticated Console task API exposes the content-free record. Local tasks
and incomplete exchanges report that no remote execution evidence is available.

## Consequences

- A released remote candidate is traceable to one complete authenticated peer
  result, exact approved disclosure, durable budget reservation, and verifier
  outcome without retaining prompt or output content in this audit record.
- Partial wire bytes cannot be resumed, verified, learned from, or released.
- A failed exchange can still leave a durable remote budget reservation because
  the attempt began. Reconciliation, crash recovery, uncertain completion, and
  unchanged-acceptance local retry remain Phase 21.6.
- Same-host two-install qualification proves the implementation boundary but not
  the two-physical-machine Phase 21.7 requirement.
