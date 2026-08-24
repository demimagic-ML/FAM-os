# Handoff 0247: Typed incident preservation and diagnosis

**Date:** 2026-07-19  
**Plan step:** Phase 30.5, 30.7, and 30.9  
**Status:** Partial (`source_composed`)  
**Previous handoff:** `0246-signed-installed-documentation-generation.md`

## Objective

Replace caller-claimed incident transitions with immutable typed evidence and
make real natural-engineering failures automatically preserve and diagnose
their evidence before returning a terminal outcome.

## Scope completed

- Added a typed, digest-bound evidence receipt for all eight incident stages.
- Added immutable receipt persistence, lookup, incident ordering, owner-codec
  encryption, and plaintext migration to the SQLite adapter.
- Natural failures now create one deterministic incident, preserve concrete
  upstream identifiers, and diagnose the failure in a restart-idempotent chain.
- The product transition surface now accepts only an already stored receipt
  whose incident and typed kind match the requested next stage.
- Added a trusted internal evidence-recording boundary for later real
  remediation, recovery, rollback, report, and closure producers.
- Exposed incident evidence read-only through natural progress, Console, and
  same-owner Shell responses.
- Added schema fixtures and adversarial tests for fabricated and wrong-stage
  evidence.

## Explicitly not completed

- Bounded repair or escalation after a failed candidate verification.
- A real remediation changeset connected to the incident.
- Monitored recovery based on post-remediation verification observations.
- Pre-commit or post-commit rollback evidence connected to the incident chain.
- Post-incident report generation and policy-backed closure.
- Signed-installed and live production-verifier incident execution.
- Host policy loading, final profile matrices, soak, or human security review.

## Architecture and decisions

ADR 0212 makes an incident transition a consequence of stored typed evidence,
not a client assertion. Core validates the receipt chain; the SQLite adapter
owns durability and encryption; product orchestration creates receipts only
from real failure outcomes; Console and Shell remain read-only observers of
that evidence.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/incident.py` | Typed evidence contract, digest, transition mapping, and chain validation. |
| `src/fam_os/adapters/sqlite/engineering_incident.py` | Immutable encrypted receipt persistence and migration. |
| `src/fam_os/product/engineering_incident_api.py` | Automatic preservation/diagnosis and trusted evidence admission. |
| `src/fam_os/product/engineering_loop_api.py` | Owner-scoped receipt query and trusted record boundary. |
| `src/fam_os/product/natural_engineering_execution.py` | Failure attachment through the real natural execution path. |
| `src/fam_os/product/natural_engineering_api.py` | Post-apply failure attachment and progress evidence. |
| `src/fam_os/console/engineering_loop_routes.py` | Authenticated read-only evidence projection. |
| `src/fam_os/shell/engineering_loop_contracts.py` | Typed Shell evidence response. |
| `tests/unit/test_engineering_incident_service.py` | Complete receipt-chain, restart, idempotence, and encryption tests. |
| `tests/integration/test_natural_engineering_incident.py` | Real verification failure, restart, and forged-evidence denial. |

## Public interfaces

- `EngineeringIncidentReceiptKind`
- `EngineeringIncidentEvidenceReceipt`
- `build_engineering_incident_receipt(...)`
- `EngineeringIncidentService.advance_with_receipt(...)`
- `ProductEngineeringLoopApi.incident_evidence_for_task(...)`
- `ProductEngineeringLoopApi.record_incident_evidence(...)` (trusted internal boundary)
- Schema `fam.core.engineering-incident-evidence`

## Validation

```bash
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_incident_service \
  tests.integration.test_natural_engineering_incident \
  tests.integration.test_console_engineering_loop \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_product_natural_engineering_api \
  tests.integration.test_product_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references \
  tests.security.test_engineering_adversarial
```

Result: 59 tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-44-07-229Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 -m unittest discover \
  -s tests/architecture -t .
```

Result: 41 architecture tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T09-45-51-946Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
git diff --check
```

Result: all 408 schema artifacts rendered and validated; diff whitespace check
passed.

## Evidence and artifacts

- ADR 0212
- The focused and architecture Larry logs listed above
- Generated `schemas/v1alpha1/fam.core.engineering-incident-evidence.schema.json`

## Known limitations and risks

- Preservation currently binds privacy-bounded upstream identifiers, not a
  retained copy of verifier output; future report policy must identify which
  sanitized diagnostics are safe and necessary to retain.
- The trusted internal evidence method must never become a raw Console/Shell
  mutation. Each remaining call site must bind a real typed producer outcome.
- These source changes postdate signed candidate
  `phase30-governance-20260719-3`; that installation does not prove them.

## Operational notes

No live service, active signed release, user repository, remote, or host policy
was changed. No incident was marked remediated, recovered, reported, or closed.

## Recommended next entry point

Add a separately approved pre-commit rollback checkpoint for post-apply
verification failure, bind its real candidate rollback receipt into the
incident, and generate a typed post-incident report. Then add bounded candidate
repair plus monitored recovery before assembling the next integrated signed
candidate.
