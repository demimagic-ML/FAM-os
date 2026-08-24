# Handoff 0231: Installed engineering loop control plane

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, and 30.9  
**Status:** Partial  
**Previous handoff:** `0230-signed-multi-attachment-allowlisted-egress.md`

## Objective

Move the persistent master engineering loop from a component-only contract into
the real unprivileged product service without allowing clients to claim that
unperformed engineering work succeeded.

## Scope completed

- Composed an owner-scoped engineering-loop API in `LocalProductService`.
- Added a dedicated WAL SQLite store under the protected product state root.
- Made the store safe for Console and Shell worker threads while retaining
  optimistic revision rejection.
- Added authenticated Console start/list/inspect/resume routes.
- Added strict versioned Shell contracts, schema roots, dispatch, client calls,
  and same-owner Unix transport tests.
- Required an active, reconfirmed, unexpired, exact task-scoped grant at start
  and before every Core-side evidence transition.
- Withheld generic stage advancement from Console and Shell because claimed
  evidence identifiers are not proof of effects.
- Added the missing representative network values so all registered schemas
  again have round-trip evidence.

## Explicitly not completed

- The receipt-driven coordinator that invokes repository planning, candidate
  editing, verification, dependencies, design, Git, deployment, evidence, and
  rollback services.
- Production checkpoint approval that triggers an exact underlying changeset or
  publication effect.
- Installed signed-artifact end-to-end qualification, both hardware profiles,
  the 24-hour soak, and independent human review.

## Architecture and decisions

ADR 0198 forbids installed clients from advancing the loop using caller-claimed
evidence. ADR 0173 remains the state-machine and authority-forgetting basis.

## Files changed

The primary additions are the product loop API/composition, Console routes,
Shell contracts/dispatch, transport and installed-product tests, four generated
Shell schemas, ADR 0198, and this handoff. The existing loop SQLite adapter now
uses a lock and `check_same_thread=False` for controlled product concurrency.

## Public interfaces

`ProductEngineeringLoopApi`, `compose_engineering_loop`,
`ShellEngineeringLoopOperation`, `ShellEngineeringLoopStartRequest`,
`ShellEngineeringLoopQuery`, `ShellEngineeringLoopMutation`,
`ShellEngineeringLoopView`, and `ShellEngineeringLoopResponse`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_master_engineering_loop \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.unit.test_fam_shell_engineering_authority_transport \
  tests.integration.test_console_engineering_loop \
  tests.integration.test_product_service_storage_modes \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.architecture.test_product_composition_boundary -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src tests
git diff --check
```

Result: 65 focused and broader affected tests passed; 379 schema artifacts
validated; compileall and `git diff --check` passed.

## Known limitations and risks

- Starting a task creates durable lifecycle state but does not start autonomous
  engineering work.
- Projections currently carry receipt identifiers, not resolved receipt bodies.
- The loop database is separate from the encrypted product database; it contains
  identifiers and counters only, never prompts, source, secrets, or receipt
  content.
- Physical allowlisted-egress qualification still requires the owner-authorized
  root broker from Handoff 0230.

## Recommended next entry point

Define a narrow receipt-validation port and a Core `EngineeringLifecycleDriver`.
Wire repository observation/planning and candidate creation first, then advance
only from the typed analysis, proposal, and candidate receipts it receives.
