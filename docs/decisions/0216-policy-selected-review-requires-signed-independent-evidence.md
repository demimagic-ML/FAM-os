# ADR 0216: Policy-selected review requires signed independent evidence

Status: Accepted

## Context

ADR 0209 made attached review findings blocking, but a task without a
checkpoint was indistinguishable from a task for which policy selected no
review. The service also accepted an arbitrary string as a resolution receipt,
and no installed reviewer recipe or owner-facing waiver ceremony existed.
Those gaps allowed the review gate to be present without proving how review was
selected, who performed it, or what evidence closed a finding.

## Decision

Core deterministically selects code, security, architecture, and design
disciplines from the admitted task intent and the exact complete changeset.
The selection is an immutable task/candidate/changeset/policy/intent-digest
record. Every modifying natural task selects code review; sensitive intent,
paths, formats, and risk codes add the other disciplines.

Only an Ed25519 release-signed reviewer recipe may satisfy the selection in the
installed product. Its reviewer identity and adapter are distinct from the
model generation producer. The bounded deterministic adapter receives the
exact candidate preview, has no filesystem, process, network, secret, or model
authority, and returns an attributable checkpoint for exactly the selected
disciplines. Core rejects an unselected, mismatched, or producer-authored
checkpoint. Apply requires the durable selection and at least one matching
non-blocking checkpoint.

A finding can be resolved only by a typed receipt bound to the exact task,
candidate, changeset, checkpoint, finding, reviewer identity, remediation
evidence, and passing verification evidence already held by Core. The former
arbitrary receipt identifier is removed.

An owner may instead waive one exact open finding. Console and Shell display
its discipline, severity, path, consequence digest, and reduced assurance.
The mutation requires explicit confirmation and a session-bound owner
authentication context. Core persists the waiver decision before changing the
checkpoint, and retries reconstruct the same decision. A waiver truthfully
reports `review_waived` or `partially_reviewed`; it never reports resolution.

The release-signed deterministic reviewer is an operational independent
reviewer boundary, not the independent human security review required by Phase
31.5.

## Consequences

- Absence of a selected review checkpoint blocks the composed apply path.
- Review discipline selection, checkpoint state, remediation receipts, and
  waiver decisions are owner-encrypted, restart-safe, and visible to Console
  and Shell.
- A model, transport caller, or owner cannot manufacture a resolution receipt.
- High-risk deterministic findings remain blocking unless trusted remediation
  evidence resolves them or the owner explicitly accepts reduced assurance.
- Signed installed and live qualification are still required before Phase 30.8
  may be marked complete.

## Alternatives considered

- Infer selection from the presence of a checkpoint. Rejected because absence
  is ambiguous and permits silent review omission.
- Accept a caller-supplied resolution identifier. Rejected because an
  identifier alone proves neither remediation nor passing verification.
- Let the generation model review its own output. Rejected because producer and
  reviewer independence would be fictional.
- Treat a release-owned reviewer as the final human security review. Rejected
  because Phase 31.5 requires independent human judgment and cannot be
  self-attested by the implementation agent.

## Evidence

- `src/fam_os/core/engineering/review_policy.py`
- `src/fam_os/core/engineering/review_recipes.py`
- `src/fam_os/adapters/review/deterministic.py`
- `src/fam_os/product/natural_engineering_review.py`
- `src/fam_os/product/natural_engineering_review_governance.py`
- `tests/integration/test_natural_engineering_checkpoint.py`
- `tests/integration/test_natural_engineering_review.py`
- `tests/unit/test_engineering_review_execution.py`

## Superseded decisions

None. This completes the selection, evidence, and owner-waiver path anticipated
by ADR 0209 while preserving its trusted-attachment boundary.
