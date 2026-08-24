# Handoff 0228: Owner-visible integration intent audit

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 owner recovery controls  
**Status:** Partial  
**Previous handoff:** `0227-intent-before-effect-integration-recovery.md`

## Objective

Expose encrypted start-intent lifecycle outcomes to the owner without adding a
new mutation or recovery authority.

## Scope completed

- Added owner-scoped intent list and exact inspection to the product facade.
- Added authenticated GET-only Console list/inspect routes.
- Added strict Shell `intent_list` and `intent_inspect` query operations.
- Added a state-validating typed Shell start-intent record.
- Extended the existing strict response schema with intent record/list shapes.
- Kept ciphertext, secret values, connector sessions, and adapter journals out
  of every response.
- Proved committed intent inspection through Console and Shell in the installed
  secret-bearing process chain.
- Proved recovered mixed intent and cleanup-receipt inspection through
  authenticated Console after real product restart recovery.
- Rendered and validated all 371 schema artifacts.

## Explicitly not completed

- Pagination or retention controls for historical start intents.
- Allowlisted egress and a shared cross-backend service network.
- Portable release-owned browser packaging.
- Independently enforced physical profiles, two-host evidence, 24-hour soak,
  and independent human review.

## Architecture and decisions

ADR 0195 makes intent audit owner-visible and strictly read-only. ADR 0194
continues to own lifecycle transitions and recovery authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/storage/integration_start_intent_repository.py` | Ordered owner intent listing |
| `src/fam_os/product/storage/integration_environment_repository.py` | Facade delegation |
| `src/fam_os/product/integration_environment_api.py` | Owner list/inspect methods |
| `src/fam_os/console/integration_start_intent_routes.py` | Authenticated GET-only audit |
| `src/fam_os/console/http.py` | Route composition |
| `src/fam_os/shell/integration_environment_contracts.py` | Strict operations and typed records |
| `src/fam_os/adapters/shell/integration_environment_dispatch.py` | Read-only dispatch |
| `src/fam_os/shell/__init__.py` | Public contract export |
| `schemas/v1alpha1/fam.shell.integration-environment-*.schema.json` | Rendered strict roots |
| `tests/integration/test_console_integration_environments.py` | Console audit coverage |
| `tests/unit/test_fam_shell_integration_environment_transport.py` | Wire/transport coverage |
| `tests/integration/test_installed_process_owner_restart_chain.py` | Installed committed-intent proof |
| `tests/integration/test_real_mixed_integration_environment.py` | Real recovered-intent proof |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt14.json` | Signed installed evidence |

## Public interfaces

- Console GET `/api/v1/engineering/environment-start-intents` and
  `/api/v1/engineering/environment-start-intents/<environment-id>`.
- Shell operations `intent_list` and `intent_inspect` under the existing
  integration-environment query/response contract version.
- `ShellIntegrationStartIntentRecord`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest <phase-27 affected modules and coverage>
PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt14.json \
  --repository . --builder-python .verification-venv/bin/python
```

Result: 97 affected tests passed in 27.964 seconds; all 41 architecture tests
passed in 0.735 seconds; all 371 schemas validated. Installed attempt 14 passed
67 tests per same-host profile label in 60.210654 seconds without checkout
imports. Wheel SHA-256:
`cd687df0a722d3625de9ae83e694f9f99df3f7b43214412c9cc9f8613f36e745`.
Signer-key SHA-256:
`a1fd3d955002657e61b14d509e9aafca11976a996e006defc7bfb70a8d0eb59b`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt14.json`
- `docs/decisions/0195-integration-start-intent-audit-is-owner-visible-and-read-only.md`

## Known limitations and risks

- List responses are currently unpaginated.
- Plans expose opaque secret reference names to their owner, never values.
- Same-host profile labels are not independent physical evidence.
- Qualification uses an ephemeral signer.

## Operational notes

Qualification left no labeled FAM container/network, process scope, temporary
build root, or process secret root.

## Recommended next entry point

Resume Phase 27.13 with exact allowlisted egress enforcement or portable
release-owned browser packaging, retaining positive and deliberate negative
installed fixtures.
