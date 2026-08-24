# Handoff 0256: Natural integration-environment composition

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 and source portions of 30.1/30.5  
**Status:** Partial  
**Previous handoff:** `0255-natural-shell-and-mcp-routing-correction.md`

## Objective

Attach the existing bounded integration-environment fabric to the same natural
task, grant, candidate, changeset, post-apply verification, commit, recovery,
Console, and Shell lifecycle used by ordinary engineering work.

## Scope completed

- Added exact natural intent recognition without treating repository text or
  model output as launch authority.
- Added a release-signed named static-web preview recipe and strict installed
  recipe loading through the existing release trust chain.
- Added a deterministic local static-preview planner that requires a regular
  candidate HTML file, loopback-only isolated networking, zero external
  destinations/secrets, and finite resource limits.
- Scoped the internal `integration-environment` coordinate in the proposed
  grant without polluting repository toolchain verification selection.
- Corrected integration authorization to the selected owner workspace while
  retaining all effects in the isolated candidate.
- Started, persisted, health-checked, cleaned, and replay-reconciled the natural
  environment through the existing owner-encrypted product API.
- Added distinct candidate and post-apply integration evidence to the durable
  master-loop state, Console projection, strict Shell view, commit evidence,
  and generated schemas.
- Bound exact ready-plus-cleaned candidate evidence into the changeset preview.
- Repeated the integration lifecycle against a fresh owner-derived clone after
  apply and blocked commit when that pass is absent or fails.
- Added a real temporary-Git natural lifecycle proving no preapproval owner
  mutation, candidate integration evidence, apply, independent post-apply
  integration evidence, local commit, and restart-readable environment state.

## Explicitly not completed

- Natural multi-service backend, browser, Docker, or local-cluster planning.
- Natural network and opaque-secret owner ceremonies.
- PostgreSQL/MySQL engineering through these environments.
- Race-free dynamic port leasing rather than bounded prelaunch selection.
- A new signed installed candidate, live-service promotion, independently
  enforced hardware profiles, soak, or human review.

## Architecture and decisions

ADR 0221 requires integration success to include both service health and exact
cleanup, binds candidate evidence into the owner checkpoint, and requires a
fresh post-apply environment before commit. Existing environment adapters and
encrypted storage remain the only execution/persistence boundaries; the
natural coordinator cannot launch a command directly.

The two new implementation files are 115 and 135 lines. The existing natural
execution/API modules remain above the preferred size threshold; this change
adds only bounded delegation and preserves their established lifecycle order.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/natural_planning.py` | Deterministic secret-free static-preview plan |
| `src/fam_os/product/natural_engineering_integration.py` | Start/cleanup/replay and post-apply coordinator |
| `src/fam_os/core/engineering/natural_language.py` | Intent and grant-tool scoping |
| `src/fam_os/core/engineering/master_loop.py` | Candidate and post-apply integration evidence |
| `src/fam_os/core/engineering/candidate_changeset_service.py` | Exact integration receipt checkpoint binding |
| `src/fam_os/product/engineering_loop_api.py` | Evidence admission, fresh owner clone, commit binding |
| `src/fam_os/product/natural_engineering_execution.py` | Candidate integration lifecycle attachment |
| `src/fam_os/product/natural_engineering_api.py` | Post-apply gate and restart projection |
| `src/fam_os/product/service.py` | Production composition |
| `src/fam_os/product/release_assembly.py` | Release-signed static preview recipe |
| `src/fam_os/shell/engineering_loop_contracts.py` | Strict receipt-ID projection |
| `src/fam_os/console/static/natural_engineering.js` | Owner-visible integration status/counts |
| `tests/integration/test_natural_integration_environment.py` | Complete natural lifecycle proof |
| `tests/unit/test_natural_integration_environment.py` | Plan, cleanup, post-apply, and replay policy |

## Public interfaces

New interfaces are `NaturalIntegrationEnvironmentPlanner`,
`NaturalEngineeringIntegrationCoordinator`,
`NaturalIntegrationEnvironmentResult`, and
`natural_integration_environment_requested`. `EngineeringLoopState`,
`EngineeringConsoleView`, and `ShellEngineeringLoopView` add separate candidate
and post-apply integration receipt-ID collections. The release expert archive
adds signed recipe `integration.python.static-http@1.0.0`.

The catalog remains at 414 schema roots; the engineering-loop and Shell schema
artifacts were regenerated for the new fields.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_natural_integration_environment tests.integration.test_natural_integration_environment tests.unit.test_natural_language_engineering tests.unit.test_candidate_changeset_service tests.unit.test_integration_environment_service tests.unit.test_integration_environment_repository tests.unit.test_product_integration_environment_api tests.unit.test_process_integration_environment tests.unit.test_docker_integration_environment tests.unit.test_mixed_integration_environment tests.unit.test_integration_environment_composition tests.unit.test_integration_environment_router tests.integration.test_process_api_integration_environment tests.integration.test_real_mixed_integration_environment tests.integration.test_docker_integration_environment tests.unit.test_master_engineering_loop tests.unit.test_product_engineering_loop_api tests.unit.test_natural_engineering_execution tests.unit.test_product_natural_engineering_api tests.integration.test_natural_engineering_checkpoint tests.integration.test_natural_database_engineering tests.integration.test_natural_runtime_diagnostics tests.unit.test_release_bundle tests.unit.test_installed_integration_recipes -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.integration.test_installed_process_owner_restart_chain tests.integration.test_process_api_integration_environment -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.unit.test_fam_shell_engineering_loop_transport tests.integration.test_console_engineering_loop -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests -q"
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: 93 broad affected tests, 3 real process/restart tests, 27
schema/Shell/Console tests, and 41 architecture tests pass. The dedicated
natural lifecycle passes. All 414 schemas validate and JavaScript/diff checks
pass. The complete source discovery executes 1,836 tests with 15 failures, no
errors, and 2 skips. All 15 failures are the pre-existing production
verifier/remote/gateway group withheld behind the unloaded root-owned
`fam-os-userns` profile. No natural integration, environment, schema, Shell, or
Console test fails.

Logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-52-21-889Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-52-07-793Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-54-58-246Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-53-07-277Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-55-49-360Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-58-42-322Z.log`

## Evidence and artifacts

- `tests/integration/test_natural_integration_environment.py`
- `docs/decisions/0221-natural-integration-health-is-changeset-and-postapply-evidence.md`
- The validation logs above.

## Known limitations and risks

- The natural planner intentionally supports only a static HTML preview.
- The current free loopback port is selected before process launch and retains
  a small local race; a later dynamic-port broker must preserve recipe and
  receipt binding.
- Source composition and real adapter regressions are not a new signed
  installed release proof.
- The active service on `127.0.0.1:8765` was not modified or restarted.

## Operational notes

No live service, release, host policy, owner repository, credential, network
broker, container, or external system changed. Real process tests used
temporary workspaces and left no active FAM scope.

## Recommended next entry point

Continue Phase 27.13 with natural multi-service planning and the separate
network/opaque-secret ceremony needed for PostgreSQL/MySQL. Start from ADRs
0219 and 0221, `src/fam_os/adapters/integration/composite_planning.py`, and
`src/fam_os/product/natural_engineering_integration.py`.
