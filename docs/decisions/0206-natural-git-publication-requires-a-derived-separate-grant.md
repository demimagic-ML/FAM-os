# ADR 0206: Natural Git publication requires a derived separate grant

**Status:** Accepted  
**Date:** 2026-07-19

## Context

The component publication service could consume an owner-supplied
`GitPublicationApproval`, but the installed engineering lifecycle had no safe
way to prepare it. A caller could otherwise invent a remote, ref, object ID,
diff digest, or credential reference, and ordinary edit authority could be
mistaken for external publication authority.

## Decision

Natural-language publication is a second ceremony after a verified local
commit. Core derives its proposal from the exact clean FAM-created local
commit, current non-protected feature ref, complete diff digest, configured
remote name, SHA-256 push-URL digest, and a credential-opaque provider
observation of the target ref and expected old object ID.

The ordinary path accepts only a new remote feature ref. Existing or protected
refs, force pushes, and reconciliation remain separate advanced workflows.

The persisted proposal contains the remote, refs, old/new objects, commits,
complete diff, verification evidence, PR text, opaque `secret.*` reference,
consequences, and a five-minute grant. That non-inheritable grant contains only
`publish` plus `secret_use`, scoped to the exact task, workspace, remote, ref,
and credential with `opaque_credential_injection`. Fresh owner authentication
bound to the final proposal is required to activate it.

Encrypted proposal state is monotonic: `prepared`, `approval_intent`,
`published`, `declined`, or `recovery_required`. Approval intent is stored
before provider effect. Restart or uncertain failure never reuses confirmation.
A successful receipt advances publication and terminal completion.

The Unix broker carries typed documents only, never credential material, and
requires a real owner- or root-owned socket with mode `0600`.

## Consequences

- A model cannot choose the remote, credential, hashes, or final authority.
- Local editing succeeds independently when publication is unavailable or
  declined; no external effect occurs.
- Existing remote refs are rejected until Phase 29.7 reconciliation is wired.
- Lost provider receipts become `recovery_required`, never an automatic retry.
- Source composition must be built, signed, installed, and exercised before
  installed maturity can be claimed.

## Alternatives considered

- Reuse ordinary modify authority: rejected because local authority must not
  imply an external effect.
- Let the model construct approval: rejected because Git and secret state are
  trusted inputs, not generative choices.
- Push before approval: rejected because publication is externally visible.
- Retry after restart: rejected because the first effect may have succeeded.

## Evidence

- `tests/integration/test_natural_engineering_publication.py`
- `tests/unit/test_git_publication_proposal_store.py`
- `tests/unit/test_unix_git_publication_broker.py`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-37-02-255Z.log`

## Superseded decisions

None. This composes and narrows the natural product use of ADR 0172.
