# Handoff 0257: Natural fixed-template multi-service composition

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 and source portions of 30.1/30.5  
**Status:** Partial  
**Previous handoff:** `0256-natural-integration-environment-composition.md`

## Objective

Advance the natural static-preview vertical slice to a real dependency-ordered
API-plus-site environment without allowing model output to choose commands,
recipes, authority, secrets, or network access.

## Scope completed

- Added release-signed fixed recipe `integration.python.root-api@1.0.0` for
  root candidate `api.py` and one exact loopback port placeholder.
- Extended deterministic natural planning to recognize explicit API, backend,
  full-stack, and web-service wording.
- Required a regular non-symlink root `api.py`; an explicit API request fails
  rather than silently claiming static-only success when it is absent.
- Composed the API before the static service with an exact dependency edge,
  fixed `/health` API observation, exact HTML health path, unique ports, and no
  network destinations, secrets, volumes, artifacts, or caller argv.
- Made the coordinator allocate the exact number of ports and reject collisions
  before environment admission.
- Extended the real temporary-Git natural lifecycle to prove two candidate
  services before approval and two fresh-owner services after apply, followed
  by cleanup, commit, and durable inspection.
- Added a real Bubblewrap/systemd integration that loads both signed recipes,
  reaches health for the API and static server, and removes both process scopes.
- Kept all existing READY/CLEANED changeset and post-apply evidence rules.

## Explicitly not completed

- A versioned declarative service manifest or framework discovery.
- More than the fixed root Python API and static-site templates.
- Natural browser, Docker, mixed-backend, or local-cluster planning.
- Natural allowlisted-network and opaque-secret owner ceremonies.
- Race-free supervisor-owned port leasing/socket activation.
- PostgreSQL/MySQL attachment, new signed installed/live proof, independently
  enforced hardware profiles, soak, or independent human review.

## Architecture and decisions

ADR 0222 keeps executable selection in the signed release and maps only narrow
natural intent plus observed regular candidate files to fixed templates. The
model can generate ordinary `api.py` content but cannot choose its interpreter,
arguments, port, health contract, dependencies, or authorities.

No component boundary changed. Planning remains in the integration adapter;
admission, authorization, persistence, execution, health, cleanup, changeset,
apply, post-apply verification, commit, Console, and Shell continue through
their existing typed services.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/natural_planning.py` | Fixed-template API/static multi-service planning |
| `src/fam_os/adapters/integration/__init__.py` | Export the root API recipe coordinate |
| `src/fam_os/product/natural_engineering_integration.py` | Exact multi-port allocation and collision rejection |
| `src/fam_os/product/release_assembly.py` | Add the release-signed root API recipe |
| `tests/unit/test_natural_integration_environment.py` | Plan, dependency, port, and coordinator policy |
| `tests/integration/test_natural_integration_environment.py` | Complete two-service natural lifecycle |
| `tests/integration/test_natural_multi_service_process.py` | Real signed process health and cleanup |
| `tests/unit/test_release_bundle.py` | Release archive recipe identity and template |
| `docs/decisions/0222-natural-multi-service-plans-use-release-owned-fixed-templates.md` | Durable executable-selection decision |

## Public interfaces

The release expert archive adds signed recipe
`integration.python.root-api@1.0.0`. The adapter package exports
`ROOT_PYTHON_API_RECIPE`. `NaturalIntegrationEnvironmentPlanner` adds
`required_port_count(...)` and accepts either one port or an exact tuple of
ports in `build(...)`.

No contract dataclass or schema root changed; the catalog remains at 414 schema
artifacts.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_natural_integration_environment tests.integration.test_natural_integration_environment tests.integration.test_natural_multi_service_process tests.unit.test_natural_language_engineering tests.unit.test_candidate_changeset_service tests.unit.test_integration_environment_service tests.unit.test_integration_environment_repository tests.unit.test_product_integration_environment_api tests.unit.test_process_integration_environment tests.unit.test_docker_integration_environment tests.unit.test_mixed_integration_environment tests.unit.test_integration_environment_composition tests.unit.test_integration_environment_router tests.integration.test_process_api_integration_environment tests.integration.test_real_mixed_integration_environment tests.integration.test_docker_integration_environment tests.unit.test_master_engineering_loop tests.unit.test_product_engineering_loop_api tests.unit.test_natural_engineering_execution tests.unit.test_product_natural_engineering_api tests.integration.test_natural_engineering_checkpoint tests.integration.test_natural_database_engineering tests.integration.test_natural_runtime_diagnostics tests.unit.test_release_bundle tests.unit.test_installed_integration_recipes tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.unit.test_fam_shell_engineering_loop_transport tests.integration.test_console_engineering_loop -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests -q"
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: 124 affected tests and all 41 architecture tests pass. The real
multi-service test takes both signed services through health and exact cleanup.
All 414 schemas validate; JavaScript and diff checks pass. Complete source
discovery executes 1,840 tests with 15 failures, no errors, and 2 skips. All 15
failures remain the production verifier/remote/gateway group correctly
withheld behind the unloaded root-owned `fam-os-userns` profile. No natural
planning, release recipe, process environment, changeset, Console, Shell, or
architecture test fails.

Logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T13-09-35-397Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T13-09-14-649Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T13-10-08-287Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T13-10-15-253Z.log`

## Evidence and artifacts

- `tests/integration/test_natural_integration_environment.py`
- `tests/integration/test_natural_multi_service_process.py`
- `docs/decisions/0222-natural-multi-service-plans-use-release-owned-fixed-templates.md`
- The validation logs above.

## Known limitations and risks

- `api.py` must implement the release-owned contract: accept its port as the
  only argument and serve HTTP health at `/health`.
- The fixed templates are intentionally not general framework discovery.
- Ports remain selected before launch, leaving the already documented bounded
  local race even though collisions inside one plan are rejected.
- Source and real adapter proof are not a new signed installed candidate.

## Operational notes

No live service, release, host policy, owner repository, credential, network
broker, container, or external system changed. The real two-service test used a
temporary candidate and removed both user systemd scopes.

## Recommended next entry point

Continue Phase 27.13 with a versioned declarative natural environment contract
that maps a bounded vocabulary to installed templates, then add an explicit
separate network/opaque-secret owner ceremony for PostgreSQL/MySQL. Start with
ADRs 0219, 0221, and 0222,
`src/fam_os/adapters/integration/composite_planning.py`, and
`src/fam_os/product/natural_engineering_integration.py`.
