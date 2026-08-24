# ADR 0202: Natural engineering effects require Core binding and two owner checkpoints

Status: Accepted

## Context

Active repository preparation ended at an isolated candidate. Allowing model
text, a Console client, or a Shell client to choose file effects, verification
recipes, current-state hashes, or Git coordinates would bypass the authority
and evidence boundaries established by the master loop.

## Decision

A natural-language engineering request first produces a non-authoritative,
visible task grant. Ordinary local mutation requires two distinct owner
checkpoints: activation of the bounded task grant and approval of the exact
verified changeset preview. Authorities such as network, publication, raw
shell, host administration, secret use, and production mutation remain separate
ceremonies and cannot be inferred from ordinary modification language.

The production inference port may return only a strict versioned candidate plan.
Core validates and binds every proposed operation to the current candidate
baseline, path policy, operation authority, and remaining budget. Core chooses
installed release-signed recipes; model output cannot supply recipe coordinates.
Every required candidate verification is recorded without advancing lifecycle
state, and the lifecycle advances only when the complete selected set passes.
Post-apply verification follows the same aggregate rule.

Proposal records and generated plans are encrypted with the owner storage key
and associated data bound to their exact identities. Legacy plaintext proposal
and generation rows migrate in place with secure deletion. Candidate edit,
verification, apply, and local Git effects retain intent-before-effect records
and restart reconciliation. Local Git delivery stages only approved paths,
binds all verification evidence, disables hooks and prompting, and recognizes
an exact already-created commit after a crash rather than replaying it.

Console and Shell are clients of the same product facade. They may display the
grant, progress, signed test receipts, complete preview, and terminal local
commit receipt, but they do not manufacture lifecycle evidence or authority.

## Consequences

- Natural language can reach an exact verified local commit without granting a
  model a terminal or a connector session.
- Failed generation or any failed required verifier stops before preview;
  failed post-apply verification prevents Git delivery.
- Restart can recover proposal activation, generation, candidate edits,
  checkpoint preparation, apply, and exact local commit without replay.
- High-risk requests fail closed pending their existing dedicated ceremonies.
- Optional publication, active rollback controls, governance services, and the
  remaining Phase 27/29 capabilities still require composition.
- Source composition is not installed proof; the signed release, host sandbox
  profile, both hardware profiles, soak, and human review remain separate gates.

## Alternatives considered

- Reusing the legacy four-file workspace patch path was rejected because it
  cannot express the master lifecycle or its evidence.
- Letting model output select commands or recipes was rejected because signed
  recipe choice is trusted policy.
- Advancing after the first passing verifier was rejected because later required
  verification could fail after the lifecycle already claimed success.
- Treating a crash after `git commit` as permission to retry the effect was
  rejected in favor of exact parent, message, path, and object reconciliation.

## Evidence

- `src/fam_os/product/natural_engineering_api.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/core/engineering/candidate_generation_service.py`
- `src/fam_os/core/engineering/local_git_delivery.py`
- `src/fam_os/adapters/shell/natural_engineering.py`
- `src/fam_os/console/static/natural_engineering.js`
- `tests/integration/test_natural_engineering_checkpoint.py`
- `tests/unit/test_local_git_delivery_service.py`
- `tests/unit/test_candidate_generation_service.py`

## Superseded decisions

None.
