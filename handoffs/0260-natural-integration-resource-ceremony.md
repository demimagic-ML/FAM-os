# Handoff 0260: Natural integration resource ceremony

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 and source portions of 30.1/30.5  
**Status:** Partial (`source_composed`; installed/live enforcement not qualified)  
**Previous handoff:** `0259-signed-installed-natural-service-composition.md`

## Objective

Replace the natural integration path's blanket rejection of network and secret
intent with a distinct exact owner ceremony that uses the existing enforcement
services without widening the ordinary task grant or `fam.integration.json`.

## Scope completed

- Added deterministic Core extraction for explicitly labelled canonical
  integration `host:port` destinations and named opaque secret references.
- Kept generic or incomplete `network`/`secret` wording fail-closed: it remains
  separately confirmed intent but creates no usable supplemental grant.
- Derived a second task-scoped `EngineeringAuthorityGrant` containing execute
  plus only the requested network/secret authorities, exact workspace,
  integration toolchain, endpoints, references, opaque exposure policy, and a
  fixed 16 MiB network ceiling.
- Preserved the ordinary natural task grant without network or secret
  authority.
- Advanced encrypted natural-proposal storage to v2 so the exact supplemental
  grant survives restart, while preserving reads and migration of v1 records.
- Added a Product coordinator that binds the complete supplemental-grant digest
  to a separate owner-authenticated transport session and requires the grant to
  be durably usable before ordinary task activation.
- Added an authenticated Console route plus distinct Console and Shell approval
  phases showing exact destinations, opaque references, byte ceiling, and
  digest before activation.
- Added a persistent grant resolver to natural environment composition. Before
  every candidate/post-apply run, the planner re-derives exact resources from
  the immutable task intent and rejects identity, authority, scope, endpoint,
  secret, exposure, or budget expansion.
- Mapped only the fixed Python API role to opaque secret references. Static-only
  secret use fails before launch.
- Reused `IntegrationEnvironmentService` for live execute, per-destination
  network, and per-reference secret authorization through the one exact
  supplemental grant.
- Added regressions for incomplete resource wording, encrypted restart,
  separate owner approval, missing usable grant, endpoint expansion, exact plan
  attachment, route session binding, and Shell checkpoint ordering.

## Explicitly not completed

- No live service, release, host policy, owner repository, secret store, network
  broker, or external endpoint changed.
- No actual credential value is created, rotated, disclosed, or embedded by
  this ceremony; referenced secrets must already exist through the separate
  secret lifecycle.
- The new natural resource path was not built into a new signed installation or
  run through the production network broker/verifier.
- Remote PostgreSQL/MySQL composition, browser/container/cluster natural
  templates, race-free port leasing, both profiles, soak, and human review
  remain open.

## Architecture and decisions

ADR 0224 establishes that natural network/secret resources remain outside the
ordinary grant and service declaration. Candidate/model output cannot request
them. The second existing public grant schema is the complete owner checkpoint,
and the planner independently re-derives its permissible scope from the
original owner intent before each environment.

The Core extraction and grant construction, adapter plan mapping, Product
ceremony, transport projections, persistent grant lookup, and execution
authorization remain separate named components. New natural-language and
adapter modules stay below the project size target.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/natural_integration_resources.py` | Exact resource extraction and supplemental grant construction |
| `src/fam_os/core/engineering/natural_language.py` | Attach resource proposal without widening ordinary scope |
| `src/fam_os/core/engineering/__init__.py` | Public deterministic resource helpers |
| `src/fam_os/adapters/sqlite/natural_engineering_serialization.py` | Encrypted proposal record v2 and v1 read compatibility |
| `src/fam_os/adapters/integration/natural_resource_planning.py` | Intent-to-grant equality and plan resource mapping |
| `src/fam_os/adapters/integration/natural_planning.py` | Allowlisted plan and API-only secret attachment |
| `src/fam_os/product/natural_engineering_integration_authority.py` | Separate owner resource ceremony and projection |
| `src/fam_os/product/natural_engineering_api.py` | Activation gate and resource-decision facade |
| `src/fam_os/product/natural_engineering_integration.py` | Usable supplemental grant resolution for each run |
| `src/fam_os/product/service.py` | Production repository/resolver composition |
| `src/fam_os/console/natural_engineering_routes.py` | Authenticated resource decision endpoint |
| `src/fam_os/console/static/natural_engineering.js` | Exact resource checkpoint UI |
| `src/fam_os/adapters/shell/natural_engineering.py` | Exact resource checkpoint in Shell |
| `tests/unit/test_natural_language_engineering.py` | Extraction and ordinary-grant separation regressions |
| `tests/unit/test_natural_engineering_store.py` | Encrypted restart persistence |
| `tests/unit/test_product_natural_engineering_api.py` | Separate ceremony and activation gate |
| `tests/unit/test_natural_integration_environment.py` | Exact plan attachment and anti-expansion policy |
| `tests/unit/test_fam_shell_natural_engineering.py` | Three-checkpoint ordering |
| `tests/integration/test_console_natural_engineering.py` | Console route/session binding |
| `docs/decisions/0224-natural-integration-resources-require-separate-exact-grants.md` | Durable permission-model decision |
| `MASTER_PLANv2.md` | Phase 27.13 and Phase 30 source evidence update |
| `MASTER_PLAN.md` | Companion-plan evidence update |
| `MASTER_PLANv2_STATUS_AUDIT.md` | Current maturity and remaining-gap update |
| `MASTER_PLANv2_COMPLETION_PROMPT.md` | Resumable baseline update |
| `docs/decisions/README.md` | ADR sequence update |
| `handoffs/README.md` | Handoff sequence update |

## Public interfaces

- Natural proposal views now contain nullable `integration_resource_grant`
  with an existing grant schema envelope, approval digest, and
  `approval_required`/`approved` status.
- Console adds POST
  `/api/v1/engineering/natural-language/proposals/{proposal_id}/integration-resource-decision`
  with exact body `{"confirmed": true}`.
- Shell adds approval capability
  `engineering.integration.resources.activate` before ordinary grant
  activation.
- Encrypted natural-proposal storage writes
  `fam.product.natural-engineering-record/v2` and reads both v1 and v2.
- No JSON Schema root changed; the generated catalog remains at 415 roots.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_natural_language_engineering tests.unit.test_natural_engineering_store tests.unit.test_natural_integration_environment tests.unit.test_product_natural_engineering_api tests.unit.test_fam_shell_natural_engineering tests.integration.test_console_natural_engineering tests.integration.test_natural_integration_environment tests.integration.test_natural_multi_service_process tests.unit.test_integration_environment_service tests.unit.test_integration_environment_repository tests.unit.test_product_integration_environment_api tests.unit.test_process_integration_environment tests.unit.test_docker_integration_environment tests.unit.test_mixed_integration_environment tests.unit.test_integration_environment_composition tests.unit.test_integration_environment_router tests.integration.test_process_api_integration_environment tests.integration.test_real_mixed_integration_environment tests.integration.test_docker_integration_environment tests.unit.test_master_engineering_loop tests.unit.test_product_engineering_loop_api tests.unit.test_natural_engineering_execution tests.integration.test_natural_engineering_checkpoint tests.unit.test_release_bundle tests.unit.test_installed_integration_recipes tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.unit.test_fam_shell_engineering_loop_transport tests.integration.test_console_engineering_loop -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests -q"
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Results:

- 136 affected tests pass.
- All 41 architecture tests pass.
- Complete source discovery runs 1,853 tests with 15 failures, no errors, and
  two skips. All 15 failures are the unchanged production-verifier,
  remote-execution, canary, and gateway group withheld downstream of the absent
  root-owned `fam-os-userns` profile. No new natural-resource or internal test
  fails.
- All 415 generated schemas validate; JavaScript syntax and diff checks pass.

Logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T13-51-28-708Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T13-51-58-798Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T13-52-47-909Z.log`

## Evidence and artifacts

- `docs/decisions/0224-natural-integration-resources-require-separate-exact-grants.md`
- `tests/unit/test_natural_integration_environment.py`
- `tests/unit/test_product_natural_engineering_api.py`
- `tests/unit/test_fam_shell_natural_engineering.py`
- The validation logs above.

## Known limitations and risks

- The initial natural syntax intentionally supports explicitly labelled
  canonical endpoints and secret references, not arbitrary prose or URLs.
- The fixed 16 MiB ceiling is visible but not yet owner-selectable within a
  smaller bounded range.
- Secret refs attach only to the one fixed Python API template.
- Existing broker/adapter tests prove enforcement components, but this handoff
  does not claim new signed-installed or live broker evidence.
- Active resource grants require owner reconfirmation after restart; a mid-task
  restart may therefore introduce another exact owner checkpoint.

## Operational notes

No live process, active release, AppArmor profile, secret, external endpoint,
network namespace, container, credential, or owner workspace changed.

## Recommended next entry point

Continue Phase 27.12/27.13 by composing a fixed PostgreSQL service template and
typed remote-database target over this exact network/opaque-secret ceremony.
Keep database migration approval, service-resource approval, changeset
approval, and production mutation as distinct checkpoints. Start with ADRs
0208, 0219, 0223, and 0224 plus the database target, integration recipe catalog,
and natural database/integration coordinators.
