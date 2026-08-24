# Handoff 0131: Durable Core repositories complete

**Date:** 2026-07-17  
**Plan step:** Phase 17.3  
**Status:** Complete  
**Previous handoff:** `0130-durable-core-repositories-partial.md`

## Objective

Replace every production Core state family needed by the unified lifecycle with
encrypted transactional repositories and persistent replay protection.

## Scope completed

- Durable requests and compare-state transition.
- Durable request, confirmation, attempt, control, and action replay.
- Encrypted authority grants, plans, ordered plan events, and policies.
- Optimistic plan revision with atomic event append.
- Encrypted final candidate, acceptance, and degradation evidence.
- Monotonic global attempt budget and reservation ledger.
- Bounded production `CoreStorageComposition` with no in-memory fallback.
- Restart, duplicate, budget, plaintext-absence, schema, and boundary tests.

## Architecture and decisions

ADR 0114 makes the durable repository set mandatory for production composition.
Seven durable Core document roots are public schemas; the catalog now has 174
artifacts.

## Validation

```bash
PYTHONPATH=src:. python3.12 -m unittest tests.unit.test_durable_core_repositories tests.unit.test_production_database tests.contract.test_schema_roundtrip tests.architecture.test_production_core_storage_boundary
PYTHONPATH=src:. python3.12 tools/render_contract_schemas.py --check
.verification-venv/bin/ruff check src/fam_os/product/storage src/fam_os/product/composition tests/unit/test_durable_core_repositories.py
PYTHONPATH=src:. .verification-venv/bin/mypy src/fam_os/product/storage src/fam_os/product/composition
```

Result: 17 focused tests passed; 174 schemas, lint, and typing pass.

## Known limitations and risks

- Action state and postcondition reconciliation are not yet implemented; Phase
  17.4 remains the authority-preserving restart gate.
- Installed product composition still uses the narrow gateway until later Phase
  17/18 service integration.

## Recommended next entry point

Implement Phase 17.4 with explicit recoverable request/action state contracts.
Safe reads and inference may resume; pending mutations lose prior approval;
uncertain actions must run postcondition reconciliation and can never be retried
from restart state alone.
