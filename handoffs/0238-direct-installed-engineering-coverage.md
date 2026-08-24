# Handoff 0238: Direct installed engineering coverage

**Date:** 2026-07-19  
**Plan step:** Phase 31.6  
**Status:** Partial (`installed_tested` subset)  
**Previous handoff:** `0237-builder-independent-signed-natural-lifecycle.md`

## Objective

Reflect the corrected signed installed natural-language evidence in the strict
integration-coverage manifest without promoting any unproven authority or exit
gate.

## Scope completed

- Added `source_composed` and `installed_tested` to the versioned maturity
  contract and generated schema.
- Advanced `engineering_authority.observe`, `.propose`, `.modify`, `.execute`,
  and `engineering_candidate_workspace` to `installed_tested` with the exact
  corrected release artifact.
- Retained explicit gaps for authority variants, specialized workflows,
  rollback, publication, matrices, soak, and review.
- Kept network, publish, raw shell, host admin, secret use, global install,
  production mutation, policy change, protected-ref write, and self-update at
  `component_tested` and not production-reachable.

## Explicitly not completed

- Phase 31.6 as a whole; the manifest remains `integration_incomplete`.
- Any coverage promotion to `operationally_proven`.
- Any authority not exercised by the exact signed installed artifact.

## Architecture and decisions

ADR 0204 preserves `operationally_proven` as the only gap-free completion
state while permitting truthful intermediate source and installation evidence.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/integration_coverage.py` | Intermediate maturity values |
| `configs/integration/coverage.json` | Five direct installed engineering rows |
| `tests/contract/test_integration_coverage.py` | Exact promotion and non-promotion policy |
| `schemas/v1alpha1/fam.product.integration-coverage.schema.json` | Generated strict enum |
| `docs/decisions/0204-integration-coverage-records-intermediate-composition-and-installation-maturity.md` | Maturity decision |

## Public interfaces

The `fam.product.integration-coverage/v1alpha1` maturity enum now also accepts
`source_composed` and `installed_tested`.

## Validation

```bash
.verification-venv/bin/python tools/render_contract_schemas.py --output schemas
.verification-venv/bin/python -m unittest \
  tests.contract.test_integration_coverage \
  tests.contract.test_schema_compatibility -v
```

All 27 targeted contract and compatibility tests pass. All evidence references
resolve inside the repository.

## Evidence and artifacts

- `artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json`
- `configs/integration/coverage.json`
- Larry log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T07-42-54-987Z.log`

## Known limitations and risks

- The v1alpha1 enum addition is intentional alpha evolution; strict decoders
  still reject all unknown values.
- Direct installed evidence covers only the ordinary local Python slice.

## Recommended next entry point

Complete explicit rollback and separately approved publication, then promote
only the newly exercised rows. Do not change program status before all rows are
gap-free and operationally proven.
