# Handoff 0087: Phase 10.1 memory lifecycle contracts

## Completed

- Reused the existing memory record, scope, provenance, retention, sensitivity, and expiry fields.
- Added deterministic active/expired/purged evaluation.
- Added owner/actor/reason-bound deletion requests.
- Added removal-confirmed deletion receipts with prior-content and tombstone digests.
- Added three public schemas; the catalog now validates 107 artifacts.
- Added strict unit and schema round-trip tests.

## Evidence

- `src/fam_os/memory/manifest.py`
- `src/fam_os/memory/lifecycle_contracts.py`
- `tests/unit/test_memory_record_manifest.py`
- `tests/unit/test_memory_lifecycle_contracts.py`
- `docs/protocols/MEMORY_RECORD_LIFECYCLE.md`
- `docs/decisions/0085-memory-deletion-needs-removal-receipt.md`

## Next

Implement Phase 10.2 session and working memory stores. Session isolation, expiry filtering, digest verification, bounded capacity, and deterministic deletion should exist before persistent document indexes.
