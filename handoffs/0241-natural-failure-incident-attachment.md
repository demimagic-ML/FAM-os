# Handoff 0241: Natural failure incident attachment

**Date:** 2026-07-19  
**Plan step:** Phase 30.7 and 30.5  
**Status:** Partial  
**Previous handoff:** `0240-separately-approved-natural-git-publication.md`

## Objective

Attach real natural-engineering failures to durable incidents and expose the
same evidence-bound state through Core, Console, and Shell without overstating
completion of the full incident-response lifecycle.

## Scope completed

- Composed the incident service into the unprivileged product engineering loop.
- Attached generation, candidate-edit, candidate-verification,
  changeset-preview, and post-apply verification failures to deterministic
  incidents using their actual evidence identifiers.
- Reconstructed task incidents in natural-language progress responses.
- Added owner-scoped Core inspection and ordered transition controls.
- Added authenticated Console incident list and confirmed advance routes.
- Added typed Shell incident list and confirmed advance contracts, wire kind,
  client call, dispatcher path, response fields, and generated schema.
- Changed installed composition to owner-bound AEAD incident documents, added a
  task index, and narrowly migrated prior plaintext component records.
- Corrected Shell post-apply re-verification dispatch so the subclass is routed
  before the initial-verification request type.

## Explicitly not completed

- Automatic evidence preservation, diagnosis, remediation proposal/application,
  recovery monitoring, incident rollback, report generation, and closure.
- Installed signed-release proof of these new controls.
- Generated-documentation and independent-review composition from Phases 30.6
  and 30.8.
- Automatic feature branching and the remaining Phase 27, 29, 30, and 31 gates.

## Architecture and decisions

ADR 0207 requires failure detection to attach only real upstream identifiers,
keeps diagnosis and remediation as later receipt-bearing transitions, and
applies the existing owner-encrypted durable-state boundary to incidents.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/incident.py` | Add task lookup, inspection, and lifecycle ownership. |
| `src/fam_os/adapters/sqlite/engineering_incident.py` | Add indexed, owner-codec-aware durable storage and migration. |
| `src/fam_os/product/engineering_incident_api.py` | Owner-scoped deterministic incident attachment. |
| `src/fam_os/product/engineering_loop_api.py` | Compose incident inspection and transition controls. |
| `src/fam_os/product/natural_engineering_execution.py` | Attach pre-apply natural failures. |
| `src/fam_os/product/natural_engineering_api.py` | Attach post-apply failures and reconstruct incidents. |
| `src/fam_os/product/composition/engineering_loop.py` | Compose the SQLite incident service. |
| `src/fam_os/product/service.py` | Supply the owner-bound incident codec. |
| `src/fam_os/console/engineering_loop_routes.py` | Add list and confirmed advance routes. |
| `src/fam_os/shell/engineering_loop_contracts.py` | Add typed incident operations and responses. |
| `src/fam_os/shell/engineering_candidate_contracts.py` | Add evidence-bound advance request. |
| `src/fam_os/adapters/shell/engineering_loop_dispatch.py` | Dispatch list/advance and correct re-verification order. |
| `src/fam_os/shell/wire.py` | Add the incident advance wire root. |
| `tests/integration/test_natural_engineering_incident.py` | Prove real failure attachment and restart persistence. |
| `tests/integration/test_console_engineering_loop.py` | Prove authenticated Console controls. |
| `tests/unit/test_fam_shell_engineering_loop_transport.py` | Prove typed Unix Shell controls. |
| `tests/unit/test_engineering_incident_service.py` | Prove ordering, encryption migration, and indexed lookup. |

## Public interfaces

- `ShellEngineeringLoopOperation.INCIDENTS`
- `ShellEngineeringLoopOperation.INCIDENT_ADVANCE`
- `ShellEngineeringIncidentAdvanceRequest`
- `ShellEngineeringLoopResponse.incident`
- `ShellEngineeringLoopResponse.incidents`
- `ShellWireKind.ENGINEERING_INCIDENT_ADVANCE`
- `GET /api/v1/engineering/tasks/{task_id}/incidents`
- `POST /api/v1/engineering/tasks/{task_id}/incident-advance`
- `fam.shell.engineering-incident-advance/v1alpha1` schema root

## Validation

```bash
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_incident_service \
  tests.integration.test_natural_engineering_incident \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_publication \
  tests.integration.test_console_engineering_loop \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.unit.test_product_natural_engineering_api \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_product_service_startup_safety \
  tests.integration.test_product_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: 59 tests passed in 7.307 seconds; `git diff --check` passed.

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: 406 schema artifacts rendered; 36 contract tests passed.

## Evidence and artifacts

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-50-17-439Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-52-01-556Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-48-24-423Z.log`
- `docs/decisions/0207-natural-failures-create-owner-encrypted-incidents.md`

## Known limitations and risks

- The current natural orchestrator stops after detection; later incident stages
  are owner-controlled typed transitions, not yet automated repair.
- Evidence identifiers are durable links; later stages still require typed
  receipt resolution before the main loop may treat them as success.
- The source checkout is heavily changed and this milestone has not been built,
  signed, installed, or promoted to the live service.

## Operational notes

No live process, active release, model, system policy, port, or owner workspace
was changed. The service on `127.0.0.1:8765` was not restarted.

## Recommended next entry point

Continue Phase 30.7 by adding trusted evidence-preservation and diagnosis
receipts to the incident orchestrator, then bind remediation to an ordinary
candidate changeset and reuse post-apply verification/rollback. Start from
`src/fam_os/product/engineering_incident_api.py` and
`src/fam_os/core/engineering/incident.py`. Keep automatic feature branching and
signed installed proof next in the Phase 30.1 spine.
