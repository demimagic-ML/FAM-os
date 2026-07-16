# Retrieval citation and provenance verifier

Each retrieved source carries a locator, provenance identity, full UTF-8 content
SHA-256, and source ID. Citations bind an exact character range and quote digest.
Claims name one or more citation IDs. Release requires every claim to have only
valid citations whose source content, locator bounds, provenance, and quote span
all verify. A source mutation, wrong quote, invalid range, or absent citation
withholds the claim and the overall result.

The public report contains IDs and reason codes, not source content. Canonical
evidence proves an exact span passes and a one-source mutation fails.
