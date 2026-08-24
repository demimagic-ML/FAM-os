# Handoff 0129: Owner-bound product encryption

**Date:** 2026-07-17  
**Plan step:** Phase 17.2  
**Status:** Complete  
**Previous handoff:** `0128-private-sqlite-wal-storage.md`

## Objective

Encrypt sensitive durable state and make missing, corrupt, or substituted keys a
visible recovery condition.

## Scope completed

- Atomic owner key creation and strict owner/mode/type/link validation.
- Key creation only for a database path that does not exist.
- Database-bound key identity in migration 0002.
- AES-256-GCM payload cipher with owner/record/field associated data.
- Explicit recovery results for missing, malformed, unsafe, or replaced keys.
- Plaintext-absence and cross-record authentication tests.

## Explicitly not completed

- Repositories begin using encrypted columns in Phase 17.3.
- Product service recovery UI and commands are composed later in Phase 17.
- External hardware-backed key storage is not required for the workstation
  baseline.

## Architecture and decisions

ADR 0113 separates key resolution from database opening and forbids transparent
replacement. `SecureStorage` is the only normal composition that yields a
database and cipher together.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/storage/keys.py` | Owner master-key lifecycle |
| `src/fam_os/product/storage/cipher.py` | Record-bound AEAD |
| `src/fam_os/product/storage/secure_store.py` | Fail-closed composition |
| `src/fam_os/product/storage/migrations/0002_master_key_binding.sql` | Key metadata |
| `tests/unit/test_secure_product_storage.py` | Recovery and confidentiality tests |
| `docs/decisions/0113-sensitive-product-state-uses-bound-aead.md` | Encryption decision |

## Public interfaces

- `OwnerKeyStore.resolve(database_exists=...)`
- `CipherContext`
- `ProductPayloadCipher.encrypt()` / `decrypt()`
- `SecureStorage.open()` and `SecureStorageResult`

## Validation

```bash
PYTHONPATH=src:. python3.12 -m unittest tests.unit.test_production_database tests.unit.test_secure_product_storage
.verification-venv/bin/ruff check src/fam_os/product/storage tests/unit/test_production_database.py tests/unit/test_secure_product_storage.py
PYTHONPATH=src:. .verification-venv/bin/mypy src/fam_os/product/storage
```

Result: 11 tests passed; lint and typing passed.

## Evidence and artifacts

- `tests/unit/test_secure_product_storage.py`
- ADR 0113
- `docs/protocols/PRODUCT_STATE_ENCRYPTION.md`

## Known limitations and risks

- File-backed owner keys protect at-rest data from accidental disclosure and
  cross-record substitution, but not from code already executing as the owner.
- Key backup/export policy still needs integration into signed product recovery.

## Operational notes

The installed daemon still does not open this store; no live user key or database
was created by these tests.

## Recommended next entry point

Implement Phase 17.3 durable repositories. Start with request replay, authority,
plan snapshots, and event append in separate bounded modules. Encode typed
contracts canonically, encrypt sensitive fields with repository-owned
`CipherContext`, and test optimistic revision and restart behavior.
