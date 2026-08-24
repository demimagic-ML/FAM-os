# ADR 0139: Training content requires explicit authority and split before synthesis

Status: Accepted

## Context

Phase 20 deliberately converts verified terminal outcomes into content-free
learning records and removes prompts, candidates, verifier feedback, and
application content during terminal commit. A real expert factory needs examples
with inputs and accepted outputs, but mining the redacted product history would
either be impossible or would require weakening an established privacy boundary.
Synthetic generation can also leak evaluation cases if a teacher receives held-
out fixtures or if descendants of one source family cross dataset partitions.

## Decision

Factory discovery remains content-free and proposal-only. Training content may
be copied only under a separate, explicit, expiring owner grant that binds the
target capability, allowed source kinds, workspace scopes, sensitivities, and
retention. Existing terminal records remain redacted.

Source families and failure clusters are assigned to train, validation, or held-
out partitions before teacher generation. Every synthetic descendant inherits
its source partition. Held-out inputs, expected outputs, verifier fixtures, and
feedback are unavailable to teachers and training workers. Every generated
example requires deterministic verification or explicit human acceptance before
it may enter a sealed dataset.

Discovery, content capture, dataset sealing, training approval, worker execution,
evaluation, package signing, installation, and activation are separate authority
boundaries.

## Consequences

- Phase 22 cannot reconstruct training examples from Phase 20 learning records.
- Useful datasets require prospective opt-in capture or independently licensed,
  approved fixtures.
- Dataset lineage must represent source families and synthetic ancestry, not only
  example hashes.
- The evaluator needs a held-out decryption boundary separate from the worker.
- More examples cannot compensate for unapproved content or detected leakage.

## Alternatives considered

- Retain every successful prompt and answer by default: rejected because it
  reverses terminal redaction and expands local sensitive-data retention.
- Let teachers generate examples before splitting: rejected because variants can
  cross partitions and expose evaluation structure.
- Treat a failure proposal as training consent: rejected by ADR 0101 and because
  observation does not grant mutation or resource authority.

## Evidence

- `src/fam_os/product/storage/terminal_outcome_repository.py`
- `src/fam_os/product/storage/terminal_redaction.py`
- `src/fam_os/product/verified_outcome_learning.py`
- `docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md`
- `MASTER_PLAN.md`, Phase 22
