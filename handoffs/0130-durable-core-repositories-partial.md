# Handoff 0130: Durable Core repositories, first slice

**Date:** 2026-07-17  
**Plan step:** Phase 17.3  
**Status:** Partial  
**Previous handoff:** `0129-owner-bound-product-encryption.md`

## Objective

Begin replacing process-local Core state with encrypted transactional
repositories that preserve replay protection across restart.

## Scope completed

- Migration 0003 for replay, authority, plan snapshot, policy, and final-evidence storage.
- Encrypted request authority repository.
- Durable request, attempt, and generic replay reservations with atomic batches.
- Encrypted optimistic-revision plan repository.
- Encrypted attempt and deadline policy repositories.
- Six additional durable Core document schemas, bringing the catalog to 173.
- Restart, atomicity, round-trip, and plaintext-absence tests.

## Explicitly not completed

- Final-evidence and global-attempt-budget repository implementations.
- Production composition swap and restart reconciliation.
- Phase 17.3 remains unchecked.

## Validation

```bash
PYTHONPATH=src:. python3.12 -m unittest tests.contract.test_schema_roundtrip tests.unit.test_production_database tests.unit.test_secure_product_storage tests.unit.test_durable_core_repositories
```

Result: 18 tests passed and 173 schemas rendered; focused lint, typing, and
whitespace checks pass.

## Recommended next entry point

Finish the typing gate, then implement encrypted final-evidence and durable
global-budget ledgers. Compose the complete repository set behind a bounded Core
storage unit before marking Phase 17.3 complete.
