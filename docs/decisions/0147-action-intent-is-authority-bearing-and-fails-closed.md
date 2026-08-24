# ADR 0147: Action intent is authority-bearing and fails closed before inference

Status: Accepted

## Context

The installed natural-language path could send an imperative machine request to
an ordinary conversation model when no application capability was selected.
The model could then describe a command and claim it had executed even though
no proposal, approval, provider invocation, postcondition, or audit existed.
The final-result policy correctly labelled the text unverified, but the ingress
route had already confused an answer candidate with an action.

Result assurance alone cannot repair that category error. The system needs a
deterministic authority boundary before model selection and distinct wire types
for answers, proposals, receipts, and unavailable capabilities.

## Decision

Core inspects every Shell, Console, declared-verifier, and delegated prompt for
action shape before ordinary inference. An action-shaped request may continue
only after it resolves to a live action capability. Missing parameters produce
an `action_proposal`; missing authority produces `capability_unavailable`; both
are model-free, content-free terminal admission outcomes. Neither may fall back
to conversational inference.

An `action_receipt` is legal only after a confirmed capability invocation and
independent postcondition verification. Core replaces any model candidate with
a deterministic receipt before release. Failed or denied action plans remain
`action_proposal` outcomes and cannot claim execution.

Final assembly requires every execute step to carry one successful action-result
reference and same-grant action-audit evidence. Passing acceptance evidence
without that execution binding is rejected, and final receipt text is derived
from the verified capability rather than candidate prose.

The first owner-filesystem vertical capability creates one empty directory
under the owner's discovered home root. Core shows the exact path and mode,
requires approval, creates through descriptor-relative no-symlink traversal,
verifies existence and emptiness, emits content-free audit records, and offers
reversal only for the same inode while it remains empty.

The result additions are published as
`fam.core.task-result/v1alpha2` and `fam.shell.snapshot/v1alpha2`. The original
`v1alpha1` roots remain byte-for-byte generated-schema compatible and have
explicit migrations. Old results migrate conservatively to conversation
answers; migration never invents action authority.

## Consequences

- A model can suggest text, but it cannot manufacture an action receipt.
- Unsupported action requests stop before model selection or runtime calls.
- Follow-up action parameters are bounded, session-scoped, expiring, and
  nonauthoritative until capability resolution and approval.
- New machine mutations require a typed capability and cannot be added by
  expanding prompt instructions.
- Existing `v1alpha1` consumers remain decodable; consumers must explicitly
  adopt `v1alpha2` to receive result-kind semantics.

## Alternatives considered

- Stronger system prompts were rejected because model compliance is not an
  authority or execution proof.
- Parsing commands from model output was rejected because it reverses the trust
  boundary and makes hallucinated execution executable.
- Treating all imperative language as conversation was rejected because the UI
  could still imply work occurred.
- Mutating the strict `v1alpha1` schemas was rejected by ADR 0018.

## Evidence

- `src/fam_os/core/production/action_intent.py`
- `src/fam_os/core/production/action_ingress_router.py`
- `src/fam_os/core/lifecycle/action_receipt_policy.py`
- `src/fam_os/product/composition/owner_filesystem.py`
- `src/fam_os/adapters/linux/scoped_directories.py`
- `tests/integration/test_verified_directory_action.py`
- `tests/unit/test_action_intent_firewall.py`
- `tests/unit/test_scoped_directories.py`
- `docs/protocols/ACTION_INTENT_FIREWALL.md`
