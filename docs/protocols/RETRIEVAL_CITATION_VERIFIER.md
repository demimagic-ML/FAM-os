# Retrieval citation and provenance verifier

Each retrieved source carries a locator, provenance identity, full UTF-8 content
SHA-256, and source ID. Citations bind an exact character range and quote digest.
Claims name one or more citation IDs. Release requires every claim to have only
valid citations whose source content, locator bounds, provenance, and quote span
all verify. A source mutation, wrong quote, invalid range, or absent citation
withholds the claim and the overall result.

Current declarations additionally bind the exact user-query SHA-256 and an
ordered set of deterministic lexical obligations. Unicode normalization,
case-folding, bounded stop-word removal, conservative stemming, and canonical
`FAM_OS`/`FAM OS`/`For All Mankind Operating System` aliasing derive those
obligations. The complete authorized source set and the exact cited spans must
cover every term. Merely citing real bytes that are unrelated to the question
cannot pass.

Candidate parsing is extractive: every claim text must be byte-identical to its
quoted source span, and the released answer must be the ordered claim texts
joined by newlines. The verifier therefore does not certify paraphrases,
inferences, summaries, semantic completeness, or factual truth beyond the exact
authorized bytes and query anchors. Such output must remain unverified unless a
future independent semantic verifier declares and proves a stronger contract.

`fam.verifier.declaration/v1alpha2` carries the query obligation. Frozen
`v1alpha1` declarations remain readable through explicit migration, but migrate
without a query obligation and cannot pass a new retrieval verification run.

The public report contains IDs, query digest/terms, missing terms, counts, and
reason codes, not source content. Canonical evidence proves an exact relevant
span passes while source mutation, paraphrase, unrelated citation, missing query
binding, and partial query coverage fail closed.
