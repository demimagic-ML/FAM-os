# Phase 20.3 signed grounded-answer qualification

Run the fresh installed gate with:

```bash
PYTHONPATH=src .verification-venv/bin/python -m tools.run_phase20_grounding_exit
```

The gate builds and signs a seven-component release, installs it privately, and
starts only the installed Python package. It proves:

- a project question fails closed before any relevant source is approved;
- FAM_OS identity is generated from the signed packaged identity resource;
- a `fam.shell`-scoped approved README reaches generation and releases a verified
  exact citation;
- a `fam.mcp`-only private document never enters a Shell generation source block;
- every current declaration binds the exact user query and requires both the
  authorized sources and cited answer spans to cover every significant query
  term;
- every answer byte is represented by an exact source-backed claim;
- the signed retrieval verifier records signed trust, package, release, digest,
  facts, and pass status;
- an active encrypted project index remains usable after service restart; and
- diagnosis is healthy and complete removal leaves no installation prefix.

Raw evidence is written to
`artifacts/memory/phase20.3-grounded-answers.json`.

## User operation

FAM_OS identity questions work without creating persistent user memory. For a
project question, first approve the relevant file or folder from FAM Console's
Memory index API. Use `application_ids: ["fam.shell"]` for Shell and Console,
or `application_ids: ["fam.mcp"]` for MCP-only retrieval. Omitting application
IDs permits any local client only when the remaining owner, purpose, workspace,
session, and expiry scope also allows it.

Ask the question as normal text. Grounded requests automatically require the
retrieval citation verifier even when the client does not select the generic
verification checkbox. Shell prints an `Exact citations` section; Console shows
the same source locator, character range, claim, and quote. If no active source
matches, FAM_OS instructs the user to approve a relevant document or folder and
does not run ungrounded inference.

Verified grounded answers are deliberately extractive. Claim text and its exact
source quote must be identical, the answer may contain only those ordered claim
texts, and both source selection and cited spans must cover the deterministic
query obligation. A real citation to unrelated product identity text therefore
cannot verify a question about runtime readiness. Paraphrased or synthesized
answers may still be useful, but this verifier does not label them verified.

Historical `fam.verifier.declaration/v1alpha1` records remain readable. They do
not contain a query obligation and cannot authorize a new verified release.
Current writes use `fam.verifier.declaration/v1alpha2`.

Phase 20.4 adds full inspect, correction, export, manual expiry, deletion, and
durable management receipts.
