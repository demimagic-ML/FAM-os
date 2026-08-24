# Handoff 0234: Durable task intent and active preparation

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, and 30.9  
**Status:** Partial active product path  
**Previous handoff:** `0233-receipt-driven-master-lifecycle-driver.md`

## Objective

Make the installed product actively perform the safe front half of engineering:
durable admission, repository understanding, architecture planning, and isolated
candidate creation.

## Scope completed

- Added exact durable task definitions and atomic definition/loop creation.
- Enforced task lifetime and complete grant-envelope containment.
- Added bounded filesystem/Git evidence observation with untrusted repository
  context and symbolic-link rejection.
- Added active Core preparation orchestration using the receipt driver.
- Committed inspection, proposal, and candidate transitions atomically only
  after candidate creation; failure leaves lifecycle state unadvanced.
- Added installed Product, Console, and Shell preparation controls.
- Projected durable intent, workspace roots, and acceptance policy.
- Excluded `.git` from candidate snapshots and denied candidate `.git` paths.
- Tested real local Git observation and candidate creation through the product
  facade.

## Explicitly not completed

- Candidate edits generated from the architecture proposal.
- Signed tool execution, repair/escalation, preview approval, reconciliation,
  commit, publication, and post-apply rollback through the active orchestrator.
- Multi-repository preparation; the active path intentionally requires one root.
- Installed signed-artifact qualification.

## Architecture and decisions

ADR 0201 makes durable exact intent and Git-metadata separation architectural
requirements. ADR 0200 remains the typed transition boundary.

## Public interfaces

`EngineeringTaskDefinition`, `engineering_task_digest`,
`EngineeringPreparationOrchestrator`, `EngineeringPreparationResult`, and
`BoundedFilesystemRepositoryObserver`; `ProductEngineeringLoopApi.prepare` is
reachable through strict Console and Shell controls.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_engineering_preparation_orchestrator \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_engineering_lifecycle_driver \
  tests.unit.test_master_engineering_loop \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.integration.test_console_engineering_loop \
  tests.integration.test_product_service_storage_modes \
  tests.contract.test_schema_roundtrip -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src tests
git diff --check
```

Result: the affected 23-test set passed; 387 schema artifacts validated;
compileall and diff checks passed.

## Known limitations and risks

- The filesystem observer intentionally produces no semantic symbol graph when
  no semantic adapter is composed; path/context planning remains bounded but
  lower fidelity.
- Git observation uses the fixed deterministic local Git adapter and fails
  closed for non-repositories or detached states.
- Candidate root storage consumption is bounded per adapter but not yet charged
  back from measured bytes into the loop budget.

## Recommended next entry point

Compose architecture-to-candidate artifact generation and signed verification,
then present the real candidate preview as the next owner checkpoint.
