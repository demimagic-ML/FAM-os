# Handoff 0232: Generated content, review, and incident governance

**Date:** 2026-07-19  
**Plan step:** Phase 30.6, 30.7, and 30.8  
**Status:** Component complete; product composition open  
**Previous handoff:** `0231-installed-engineering-loop-control-plane.md`

## Objective

Define enforceable governance for generated documentation, independent review,
and engineering incidents before wiring them into the installed master loop.

## Scope completed

- Added candidate-bound generation requests for diagrams, API references,
  runbooks, changelogs, and generated code.
- Bound receipts to exact sources, output digest, generator recipe, ownership,
  and authoritative regeneration instructions.
- Added deterministic source/output staleness reports and strict requirement
  traceability.
- Added independent code/security/architecture/design review checkpoints with
  typed findings, optimistic SQLite persistence, blocking passage, receipt-bound
  resolution, and exact-consequence truthful waivers.
- Added a hash-chained optimistic incident lifecycle covering detection,
  evidence preservation, diagnosis, remediation proposal/application, monitored
  recovery, rollback, reporting, and closure.
- Registered and rendered all new public schemas.

## Explicitly not completed

- Installed product composition, Console/Shell projections, and master-loop
  invocation of these services.
- Signed generator recipe implementations and physical generated-output tools.
- Independent human review required by Phase 31.5.

## Architecture and decisions

ADR 0199 makes receipt binding, truthful waiver assurance, and restart-safe
incident chronology durable policy.

## Public interfaces

The new public surfaces are the `Documentation*`, `GeneratedDocumentation*`,
`RequirementTrace*`, `EngineeringReview*`, and `EngineeringIncident*` contracts
and services, plus `SQLiteEngineeringReviewStore` and
`SQLiteEngineeringIncidentStore`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_governed_documentation \
  tests.unit.test_engineering_review_service \
  tests.unit.test_engineering_incident_service \
  tests.contract.test_schema_roundtrip -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src tests
git diff --check
```

Result: 13 focused tests passed; 386 schema artifacts validated; compileall and
diff checks passed.

## Known limitations and risks

- Owner authentication of review waivers belongs in the future product facade;
  the Core contract already binds the authentication context and consequences.
- Receipt identifiers are contract links; the master driver must resolve and
  validate the typed receipts before advancing the main loop.
- No operational coverage status was promoted.

## Recommended next entry point

Add the Core receipt-validation registry and lifecycle driver, then compose
documentation, review, and incident stores beside the engineering loop in the
unprivileged product service.
