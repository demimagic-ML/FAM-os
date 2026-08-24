# Handoff 0258: Versioned natural service declaration

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 and source portions of 30.1/30.5  
**Status:** Partial  
**Previous handoff:** `0257-natural-fixed-template-multi-service-composition.md`

## Objective

Replace implicit-only natural multi-service topology with a versioned,
owner-visible, model-proposable contract that cannot select executable policy
or exceed the natural task's admitted intent.

## Scope completed

- Added strict public `NaturalIntegrationEnvironmentDeclaration`, service
  declaration, and closed service-template contracts.
- Registered and generated schema
  `fam.core.natural-integration-declaration/v1alpha1`.
- Added bounded no-follow loading from fixed candidate path
  `fam.integration.json` through the standard strict schema codec.
- Limited declarations to logical IDs, the `python_api`/`static_site` enum, and
  an acyclic dependency graph; recipes, commands, ports, network, secrets,
  images, volumes, health settings, and budgets are structurally impossible.
- Required declaration roles to remain subordinate to exact natural intent:
  API declarations need API/backend/full-stack/web-service wording; API-only
  tasks cannot implicitly run a site; site/page/full-stack tasks cannot omit
  their static service.
- Preserved the heuristic plan when no declaration exists for backwards
  compatibility with the initial source slice.
- Added a system-owned generation hint containing the schema envelope and role
  example without disclosing or inviting recipe coordinates.
- Extended the complete natural Git lifecycle so the generated declaration is
  checkpointed, applied, decoded from the owner tree, rerun from a fresh clone,
  committed, and durably inspected.
- Added duplicate-key, intent-overreach, duplicate-template, dependency-cycle,
  logical-ID/dependency mapping, and API-only least-authority regressions.

## Explicitly not completed

- Additional declaration templates beyond root Python API and static site.
- Arbitrary source entrypoints, framework discovery, Docker Compose, or caller
  commands.
- Browser, container, mixed-backend, and local-cluster natural planners.
- Network, opaque-secret, and remote-database owner ceremonies.
- Race-free Supervisor port leasing/socket activation.
- A new signed installed/live candidate, independently enforced profile rows,
  soak, or independent human review.

## Architecture and decisions

ADR 0223 makes the candidate declaration public versioned data while keeping
it subordinate to Core intent and release-owned template selection. It is an
ordinary candidate artifact and gains no privileged interpretation: all effects
still flow through the existing grant, permit, environment adapter, health,
cleanup, changeset, apply, post-apply, commit, and rollback services.

The schema/codec boundary performs exact field, enum, duplicate-key, and version
validation. The integration adapter performs candidate-file and intent-to-role
validation. Core's contract remains independent of filesystem and execution
implementations.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/natural_integration_declaration.py` | Versioned service-graph contract and invariants |
| `src/fam_os/core/engineering/__init__.py` | Public contract exports |
| `src/fam_os/adapters/integration/natural_declaration.py` | Bounded strict candidate loader |
| `src/fam_os/adapters/integration/natural_planning.py` | Intent-subordinate declaration mapping |
| `src/fam_os/core/engineering/candidate_generation_service.py` | System-owned schema hint for natural generation |
| `src/fam_os/schemas/catalog.py` | Public root registration |
| `schemas/v1alpha1/fam.core.natural-integration-declaration.schema.json` | Generated JSON Schema |
| `tests/contract/schema_integration_environment_fixtures.py` | Representative schema document |
| `tests/contract/test_schema_roundtrip.py` | Catalog-wide round-trip inclusion |
| `tests/unit/test_natural_integration_environment.py` | Declaration and least-authority policy |
| `tests/unit/test_candidate_generation_service.py` | Prompt-vocabulary boundary |
| `tests/integration/test_natural_integration_environment.py` | Generated declaration through commit |
| `docs/decisions/0223-natural-service-declarations-are-versioned-intent-subordinate-data.md` | Durable contract decision |

## Public interfaces

New public contracts are `NaturalIntegrationEnvironmentDeclaration`,
`NaturalIntegrationServiceDeclaration`, and
`NaturalIntegrationServiceTemplate`. Public constants identify
`fam.integration.json` and
`fam.core.natural-integration-declaration/v1alpha1`.

The generated schema catalog now contains 415 roots. No existing schema changed
shape.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_natural_integration_environment tests.integration.test_natural_integration_environment tests.integration.test_natural_multi_service_process tests.unit.test_candidate_generation_service tests.unit.test_natural_language_engineering tests.unit.test_candidate_changeset_service tests.unit.test_integration_environment_service tests.unit.test_integration_environment_repository tests.unit.test_product_integration_environment_api tests.unit.test_process_integration_environment tests.unit.test_docker_integration_environment tests.unit.test_mixed_integration_environment tests.unit.test_integration_environment_composition tests.unit.test_integration_environment_router tests.integration.test_process_api_integration_environment tests.integration.test_real_mixed_integration_environment tests.integration.test_docker_integration_environment tests.unit.test_master_engineering_loop tests.unit.test_product_engineering_loop_api tests.unit.test_natural_engineering_execution tests.unit.test_product_natural_engineering_api tests.integration.test_natural_engineering_checkpoint tests.integration.test_natural_database_engineering tests.integration.test_natural_runtime_diagnostics tests.unit.test_release_bundle tests.unit.test_installed_integration_recipes tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.unit.test_fam_shell_engineering_loop_transport tests.integration.test_console_engineering_loop -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests -q"
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: 134 affected tests and all 41 architecture tests pass. All 415 schemas
validate; JavaScript and diff checks pass. Complete source discovery executes
1,845 tests with 15 failures, no errors, and 2 skips. All 15 failures remain the
production verifier/remote/gateway group correctly withheld behind the unloaded
root-owned `fam-os-userns` profile. No declaration, generation, natural
integration, release recipe, process environment, changeset, Console, Shell,
schema, or architecture test fails.

Logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T13-23-30-990Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T13-20-14-573Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T13-24-08-747Z.log`

## Evidence and artifacts

- `schemas/v1alpha1/fam.core.natural-integration-declaration.schema.json`
- `tests/integration/test_natural_integration_environment.py`
- `tests/integration/test_natural_multi_service_process.py`
- `docs/decisions/0223-natural-service-declarations-are-versioned-intent-subordinate-data.md`
- The validation logs above.

## Known limitations and risks

- The declaration currently provides topology for two fixed templates, not a
  general process or container manifest.
- Candidate `api.py` still owns application behavior and must accept the fixed
  port argument and `/health` contract.
- Ports remain selected before launch and retain the documented bounded race.
- Source and real-adapter proof are not a new signed installed candidate.

## Operational notes

No live service, release, host policy, owner repository, credential, network
broker, container, or external system changed. Real process tests used only
temporary candidates and left no FAM scope active.

## Recommended next entry point

Continue Phase 27.13 by adding a browser observation template over the existing
bounded DevTools client, then design the separate explicit network/opaque-secret
ceremony needed for remote databases. Start with ADRs 0188, 0219, and 0223,
`src/fam_os/adapters/integration/devtools_client.py`, and
`src/fam_os/product/natural_engineering_integration.py`.
