# ADR 0150: Verified retrieval is query-bound and extractive

Status: Accepted

## Context

The retrieval verifier proved authorized source identity, full-content digest,
exact quote range, quote digest, and claim-to-citation linkage. It did not prove
that those genuine bytes answered the current question. An installed request
asking whether the local residency smoke was ready mentioned `FAM_OS`; source
selection chose the packaged identity document, the model returned an identity
sentence, and the exact-citation verifier labelled that unrelated answer
verified.

This was a verification-contract defect, not merely weak model quality. Stronger
models could reduce the frequency but could not make the old acceptance rule
sound.

## Decision

Current retrieval declarations use `fam.verifier.declaration/v1alpha2` and bind:

- the SHA-256 of the exact user query bytes; and
- one to 32 ordered unique canonical lexical obligations.

Obligations are derived deterministically with Unicode NFKC normalization,
case-folding, bounded stop-word removal, conservative ASCII stemming, and one
canonical identity alias for `FAM_OS`, `FAM OS`, and `For All Mankind Operating
System`.

Before inference, the complete authorized source set must cover every required
term. At verification, the exact cited spans must independently cover every
term. Candidate claims are extractive: each claim text is byte-identical to its
source quote and the answer is exactly the ordered claim texts joined by newline
bytes. A current declaration without a query obligation fails closed.

The frozen `fam.verifier.declaration/v1alpha1` shape remains registered for
durable-data compatibility. Explicit migration preserves readability and sets
no query obligation; such a record cannot pass a new verification run.

## Consequences

- A genuine but irrelevant citation no longer produces a verified answer.
- Source insufficiency fails before model inference and explains how to approve
  a relevant document.
- Exact identity questions remain usable under every documented product-name
  spelling.
- Synonym-only, paraphrased, inferred, or summarized answers can be conservatively
  withheld even when a human would consider them supported.
- `verified` now means exact authorized extraction plus deterministic query-anchor
  coverage. It does not mean semantic completeness or general factual truth.
- A future abstractive verifier must introduce an independent declared contract;
  it cannot weaken this one in place.

## Alternatives considered

- Relying on a stronger model was rejected because generation quality cannot
  repair an unsound acceptance predicate.
- Checking query terms only during source selection was rejected because the
  model could still cite a different, irrelevant span from a broad source.
- Accepting arbitrary claim paraphrases was rejected because exact citations do
  not deterministically prove that a paraphrase preserves meaning.
- Mutating the old declaration schema was rejected because signed durable
  payloads require an explicit frozen legacy contract and migration.

## Evidence

- `src/fam_os/verification/retrieval.py`
- `src/fam_os/verification/retrieval_candidate.py`
- `src/fam_os/verification/legacy_declarations.py`
- `src/fam_os/product/grounded_retrieval.py`
- `src/fam_os/core/production/grounded_result.py`
- `tests/unit/test_retrieval_citation_verifier.py`
- `tests/unit/test_retrieval_candidate.py`
- `tests/unit/test_product_grounded_retrieval.py`
- `tests/unit/test_contract_payload_migration.py`
- `tests/integration/test_production_verifier_bindings.py`
