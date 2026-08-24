# Handoff 0174: Query-bound extractive grounding

**Date:** 2026-07-18  
**Plan step:** Phase 23 audit correction for Phases 8.6 and 20.3  
**Status:** Complete in source and signed installed smoke; broad Phase 23 gates remain  
**Previous handoff:** `0173-production-residency-and-confirmed-eviction.md`

## Objective

Prevent an exact but irrelevant citation from being released as a verified
answer, while preserving durable legacy declaration readability and installed
identity usability.

## Defect reproduced

The installed prompt `is the local FAM_OS residency smoke ready?` selected the
packaged identity source only because it mentioned FAM_OS. The model answered
with the product-name expansion. Exact span and digest checks passed even though
the answer did not address residency readiness. The false `verified` label was
therefore caused by an incomplete acceptance contract.

## Scope completed

- Bound current retrieval declarations to the exact query SHA-256 and bounded
  deterministic required terms.
- Required the full authorized source set to cover the query obligation before
  inference.
- Required exact verified cited spans to cover the same obligation at release.
- Required every claim text to equal its source quote byte-for-byte and every
  answer byte to come from ordered claims.
- Canonicalized FAM_OS, FAM OS, and the full product name to one identity term.
- Added source/answer coverage reason codes and content-free durable query facts.
- Added a frozen `v1alpha1` declaration contract and explicit migration to
  query-unbound current data that remains readable but cannot newly verify.
- Advanced current declarations to `fam.verifier.declaration/v1alpha2` without
  changing the existing retrieval result or expert result schemas.
- Updated signed verifier artifact digests and registered both declaration
  schema versions.
- Built a complete dependency wheelhouse, after an incomplete wheelhouse was
  correctly rejected by the atomic updater health check.
- Atomically activated signed release `fam-os-query-bound-20260718-02` and ran
  the service from its installed active Python tree.

## Live installed evidence

- Clean offline dependency installation imported only the temporary installed
  wheel and canonicalized the full product name to `famos`.
- Atomic update diagnosis reported healthy with no issues and the active link
  resolved to `releases/fam-os-query-bound-20260718-02`.
- `What is FAM_OS?` selected Laguna, returned only two exact packaged source
  claims, passed the signed verifier, and exposed both exact citations.
- The previous residency-smoke prompt returned the no-approved-source response
  before inference; it did not receive the identity answer or a verified label.
- The restartable user service loaded `PYTHONPATH` from the installed active
  tree, remained active after the denial, and served Console HTTP 200.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/verification/retrieval.py` | Query obligations and source/span coverage. |
| `src/fam_os/verification/retrieval_candidate.py` | Strict extractive candidate parsing. |
| `src/fam_os/verification/declarations.py` | Current query-bound declaration. |
| `src/fam_os/verification/legacy_declarations.py` | Frozen legacy declaration and migration. |
| `src/fam_os/verification/domain_adapters.py` | Query-aware verifier and evidence facts. |
| `src/fam_os/verification/generation.py` | Exact-extraction generation contract. |
| `src/fam_os/product/grounded_retrieval.py` | Query-complete authorized source selection. |
| `src/fam_os/core/production/grounded_result.py` | Reject new query-unbound results. |
| `src/fam_os/product/storage/contract_payload.py` | Legacy durable migration. |
| `src/fam_os/schemas/catalog.py` | Frozen v1 and current v2 schema registration. |
| `src/fam_os/experts/retrieval_tiers.py` | Query-aware expert-tier verification. |
| `src/fam_os/adapters/ollama/retrieval_synthesizer.py` | Extractive tier synthesis. |
| `configs/packages/verifiers/` | Current verifier-tree artifact digest. |
| `configs/packages/verifier-bindings/` | Matching signed binding digest. |

## Validation

```bash
.verification-venv/bin/python -m unittest \
  tests.unit.test_product_grounded_retrieval \
  tests.unit.test_retrieval_citation_verifier \
  tests.unit.test_retrieval_candidate \
  tests.unit.test_retrieval_tiers \
  tests.unit.test_production_task_gateway \
  tests.unit.test_contract_payload_migration \
  tests.integration.test_production_verifier_bindings

larry run ./.verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check src tests tools connectors/vscode/test
.verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
git diff --check
```

All 35 focused tests passed. The complete source suite passed 1,245 tests with
two declared environment/hardware skips. Repository-wide Ruff and diff checks
passed, and all 286 generated schema artifacts validate. The full-suite log is
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T08-15-08-997Z.log`.

## Known limitations and risks

- Lexical coverage is deliberately conservative and can reject synonym-only or
  otherwise valid abstractive answers.
- Exact extraction does not prove that an authorized source is globally true or
  complete; it proves byte provenance and query-anchor coverage.
- The live installed smoke is not the clean-profile matrix, 24-hour soak,
  independent security review, rollback, recovery, or removal evidence required
  by Phase 23.
- The ephemeral signing key used for this owner smoke is not a production trust
  anchor.

## Recommended next entry point

Refresh both code maps and continue the Master Plan audit from the remaining
Phase 23 source and evidence gaps. Keep
clean-profile, physical-matrix, soak, review, rollback, and removal requirements
explicitly uncompleted until direct evidence exists.
