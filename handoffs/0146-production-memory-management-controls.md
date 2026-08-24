# Handoff 0146: Production memory management controls

**Date:** 2026-07-17  
**Plan step:** Phase 20.4  
**Status:** Complete  
**Previous handoff:** `0145-production-grounded-answers.md`

## Objective

Give the authenticated owner complete Shell and Console control over persistent
document memory, with atomic encrypted receipts and fresh signed installed
evidence.

## Scope completed

- Added strict inspect, export, correction, document deletion, manual grant
  expiry, and durable management-receipt contracts and rendered schemas.
- Added owner-wide management authority independent from purpose, application,
  session, and workspace retrieval restrictions.
- Added source-digest concurrency to correction and deletion. Correction retains
  provenance and re-embeds the bounded replacement with the original model.
- Added an encrypted SQLite receipt repository and migration. Every mutation and
  receipt commit atomically; receipts survive document and grant removal.
- Added durable request-ID replay, including exact replay after restart and
  conflict rejection when an ID is reused for another operation or target.
- Composed one production management service into the document-index service,
  Console HTTP API, FAM Shell peer transport, controller, and terminal.
- Added the Console Memory ledger for inspect, export, correction, deletion,
  expiry, and receipt history with visible confirmations.
- Added bounded Shell pages, safe terminal rendering, literal `--confirm`, and a
  bounded `O_NOFOLLOW` strict-UTF-8 correction-file reader.
- Added focused contract, unit, Console HTTP, product integration, migration,
  encryption, restart, and fresh installed qualification coverage.

## Explicitly not completed

- Phase 20.5-20.7 verified-outcome adaptation, live prediction/scheduling, and
  disable/reset/drift/rollback controls.
- Phases 21-23 trusted physical peers, the real Expert Factory, and final release
  qualification.

## Architecture and decisions

ADR 0128 separates owner management authority from retrieval authority and
requires explicit confirmed mutations, current-content digests, atomic encrypted
receipts, and durable request identity. Console and Shell are two authenticated
clients of the same service; neither delegates durable memory mutation to a
model. Receipts prove a mutation without retaining recoverable deleted payloads.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/memory/management.py` | Strict management requests, inspections, exports, and receipts. |
| `src/fam_os/product/storage/document_management_repository.py` | Atomic encrypted mutations and receipts. |
| `src/fam_os/product/document_management_service.py` | Production authority, preparation, retries, and replay. |
| `src/fam_os/console/memory_routes.py` | Authenticated Console memory API. |
| `src/fam_os/console/static/memory.js` | Interactive owner memory ledger. |
| `src/fam_os/shell/memory_contracts.py` | Bounded Shell request and response contracts. |
| `src/fam_os/adapters/shell/memory_dispatch.py` | Peer transport dispatch to the production service. |
| `src/fam_os/shell/memory_terminal.py` | Explicit terminal management commands. |
| `tools/phase20_management_exit/` | Fresh installed qualification implementation. |
| `artifacts/memory/phase20.4-memory-management.json` | Passing signed evidence. |

## Public interfaces

- Contract `fam.memory.management/v1alpha1`
- Contracts `fam.shell.memory-query/v1alpha1` and
  `fam.shell.memory-response/v1alpha1`
- Console `/api/v1/memory/*` owner endpoints
- Shell `/memory list|inspect|export|correct|delete|expire|receipts`
- `tools/run_phase20_management_exit.py`

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/contract -t .
.verification-venv/bin/ruff check src tests tools connectors/vscode/test
MYPYPATH=src:tools .verification-venv/bin/mypy --explicit-package-bases <28 affected targets>
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/app.js
node --check src/fam_os/console/static/memory.js
PYTHONPATH=src:tools .verification-venv/bin/python tools/run_phase20_management_exit.py
git diff --check
```

Results: 975 tests pass with two declared skips; 39 architecture tests, 35
contract tests, 28 affected Mypy targets, whole-tree Ruff, 199 schema artifacts,
both JavaScript syntax checks, and diff checks pass. A fresh Ed25519-signed
seven-component installation reports `passed: true`, persists corrections and
six encrypted receipts across restart, supports exact mutation replay, contains
none of the test plaintext nonces in SQLite or WAL, diagnoses healthy, and
removes completely.

## Evidence and artifacts

- `artifacts/memory/phase20.4-memory-management.json`
- `tests/unit/test_product_document_management_service.py`
- `tests/unit/test_fam_shell_memory.py`
- `tests/unit/test_fam_shell_memory_transport.py`
- `tests/integration/test_console_memory_management.py`
- `tests/integration/test_product_service.py`
- `docs/decisions/0128-persistent-memory-mutations-are-owner-controlled-and-receipt-bound.md`
- `docs/operations/PHASE20_MEMORY_MANAGEMENT.md`

## Known limitations and risks

- Correcting retained memory does not modify its original source file. A later
  approved re-index may replace the correction.
- Receipts prove product database state transitions; they are not independently
  notarized external audit records.
- Automatic TTL expiry remains lifecycle cleanup and does not create a manual
  owner receipt.
- Phase 23 still owns clean-machine CPU-only and full-workstation matrices.
- The qualification signing key is ephemeral evidence, not a production trust
  anchor.

## Operational notes

Use the current digest printed by inspect/export for correction and deletion.
Retain the request ID when retrying a mutation after a lost response. Mutation
failures caused by a stale digest require re-inspection, not blind retry.

## Recommended next entry point

Begin Phase 20.5 by tracing the installed verified result and acceptance-evidence
repositories. Define the minimal derived learning record and explicit exclusion
of raw prompts before connecting any adaptation consumer.
