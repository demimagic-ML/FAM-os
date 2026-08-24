# ADR 0204: Integration coverage records intermediate composition and installation maturity

Status: Accepted

## Context

MASTER_PLANv2 completion discipline distinguishes `source_composed` and
`installed_tested`, but the versioned integration-coverage contract jumped from
`component_tested` or `acceptance_only` directly to `production_wired`. The
manifest therefore could not truthfully record the new signed natural-language
evidence without either understating production reachability or overstating it
as fully production-wired.

## Decision

`IntegrationMaturity` and its generated schema admit `source_composed` and
`installed_tested` as explicit intermediate states. These values do not change
the completion predicate: only `operationally_proven`, production-reachable,
installed, gap-free rows satisfy final program completion.

Coverage rows may advance only when a repository-resident direct artifact names
the exact signed installed candidate and the row retains every unproven scope in
`known_gaps`. The Phase 30 corrected installed artifact advances only ordinary
`observe`, `propose`, `modify`, `execute`, and the candidate workspace. All ten
specialized engineering authorities remain `component_tested`.

## Consequences

- Coverage can express actual progress without collapsing installed smoke proof
  into operational completion.
- Direct evidence and known gaps remain machine-readable per subsystem.
- Final Phase 31.6 remains open until every required row reaches
  `operationally_proven` from the exact final candidate.

## Alternatives considered

- Leave proven rows `component_tested`: rejected because it contradicts direct
  installed evidence and hides production reachability.
- Promote proven rows to `production_wired`: rejected because publication,
  rollback, specialized operations, profiles, soak, and review remain open.
- Use free-form maturity strings: rejected because coverage is a strict
  versioned contract.

## Evidence

- `src/fam_os/product/integration_coverage.py`
- `configs/integration/coverage.json`
- `tests/contract/test_integration_coverage.py`
- `schemas/v1alpha1/fam.product.integration-coverage.schema.json`
- `artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json`

## Superseded decisions

None.
