# Handoff 0144: Production expiring document indexing

**Date:** 2026-07-17  
**Plan step:** Phase 20.2  
**Status:** Complete  
**Previous handoff:** `0143-production-ephemeral-session-memory.md`

## Objective

Make persistent local document and folder indexing reachable from the installed
product only through explicit, bounded, expiring user authority, with encrypted
restart-safe storage and safe filesystem traversal.

## Scope completed

- Added typed file/folder grants and indexing receipts with owner scope, safe
  extension subset, recursion, file/byte bounds, model provenance, and a maximum
  90-day expiry.
- Extended per-document approvals with grant and expiry binding while preserving
  the earlier component contract.
- Replaced raw positional index rows with typed repository records and a protocol
  shared by the component and product repositories.
- Added ProductDatabase migration 0011 and an owner-bound AEAD repository for
  grants, approvals, chunks, content, and embeddings.
- Added descriptor-relative `openat` traversal with held directory handles,
  `O_NOFOLLOW`, regular/single-link/owner checks, stable-read checks, strict
  UTF-8, deterministic traversal, and hard scan/file/byte limits.
- Added atomic ingestion and expiry cascade cleanup at startup, access, and from
  a supervised lifecycle worker.
- Bound embedding to the enabled signed release model and its actual local
  manifest digest.
- Added authenticated, Origin/CSRF-protected Console create/list endpoints.
  Client JSON cannot select owner, approver, grant ID, model, artifact digest,
  approval time, or absolute expiry; unknown fields fail closed.
- Added unit, contract, storage, product restart, Console, and signed installed
  qualification coverage.

## Explicitly not completed

- Phase 20.3 retrieval injection and exact local citations.
- Phase 20.4 correction/export/manual-expiry/delete UI and durable management
  receipts.
- Phase 20.5-20.7 verified-outcome learning, scheduling adaptation, and drift
  controls.
- Phases 21-23.

## Architecture and decisions

ADR 0126 separates persistent path authority from default session memory. The
ProductDatabase is the only production persistence location. Filesystem access
is descriptor-relative and the index is byte-digest-bound. Expiry is both an
access policy and a payload-deletion event. Direct database retrieval from Core
is forbidden; Phase 20.3 must use the typed repository and scope boundary.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/memory/grant_contracts.py` | Expiring path grants and receipts. |
| `src/fam_os/memory/document_ingestion.py` | Bounded descriptor-safe ingestion. |
| `src/fam_os/product/storage/document_index_repository.py` | Product AEAD persistence. |
| `src/fam_os/product/storage/migrations/0011_document_indexes.sql` | Durable schema. |
| `src/fam_os/product/document_index_service.py` | Server-owned policy and expiry worker. |
| `src/fam_os/console/http.py` | Authenticated Console create/list routes. |
| `tools/phase20_index_exit/` | Installed qualification components. |
| `artifacts/memory/phase20.2-document-indexing.json` | Passing signed evidence. |

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check .
.verification-venv/bin/python -m unittest discover -s tests/architecture -t .
.verification-venv/bin/python -m unittest discover -s tests/contract -t .
MYPYPATH=src .verification-venv/bin/mypy --explicit-package-bases <affected modules>
.verification-venv/bin/python tools/run_phase20_index_exit.py
```

Results: 948 Python tests pass with two declared skips; 39 architecture tests,
34 contract tests, Ruff, and 13 affected Mypy modules pass. A fresh signed
seven-component installation reports `passed: true`, with empty-by-default and
unconfirmed-denial evidence, two safely indexed allowed documents, symlink and
extension exclusion, short-grant cascade expiry, active-grant restart
persistence, no plaintext nonce in database/WAL files, healthy diagnosis, and
complete removal.

The schema renderer updated every registered schema. Its global command still
reports the two pre-existing unregistered custom configuration artifacts
`fam.product.fallbacks-config` and `fam.product.mcp-ingress-config`; this is not
caused by the document contracts and remains a repository validation gap.

## Evidence and artifacts

- `artifacts/memory/phase20.2-document-indexing.json`
- `tests/unit/test_document_index_grants.py`
- `tests/unit/test_secure_document_ingestion.py`
- `tests/unit/test_product_document_index_repository.py`
- `tests/unit/test_product_document_index_service.py`
- `tests/integration/test_product_service.py`
- `tests/integration/test_console_http.py`
- `docs/decisions/0126-persistent-document-indexing-requires-expiring-path-grants.md`
- `docs/operations/PHASE20_DOCUMENT_INDEXING.md`

## Known limitations and risks

- Phase 20.2 stores approved knowledge but deliberately does not make generated
  answers consume it; Phase 20.3 owns grounding and citation release policy.
- The installed embedding runtime is deterministic qualification evidence;
  Phase 23 owns the real-model CPU and workstation matrices.
- Full management UI and durable user deletion receipts remain Phase 20.4.
- The signing key is ephemeral qualification evidence, not a production trust
  anchor.

## Recommended next entry point

Begin Phase 20.3 by adding a retrieval port to the production worker. Select
only active records matching the trusted owner/purpose/application/workspace
context, inject bounded content as untrusted evidence, produce byte-bound source
citations, and withhold identity/project claims unless the citation verifier
passes.
