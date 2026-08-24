# Phase 20.4 persistent memory management

FAM Console exposes the owner memory ledger under **Control → Memory**. It lists
retained documents and durable receipts, opens document metadata, exports the
retained copy, and presents explicit controls for correction, deletion, and
grant expiry. All mutations require the authenticated Console session, a valid
same-origin CSRF token, and visible confirmation.

Correction changes the encrypted copy retained by FAM_OS; it does not edit the
original file. Re-indexing that file later is a separate approved operation.

## FAM Shell commands

```text
/memory list [OFFSET] [LIMIT]
/memory inspect DOCUMENT_ID
/memory export DOCUMENT_ID
/memory correct DOCUMENT_ID EXPECTED_SHA256 REPLACEMENT_FILE --confirm
/memory delete DOCUMENT_ID EXPECTED_SHA256 --confirm
/memory expire GRANT_ID --confirm
/memory receipts [OFFSET] [LIMIT]
```

`correct` accepts one regular, non-symlink, strict UTF-8 file no larger than the
document contract limit. `EXPECTED_SHA256` comes from list, inspect, or export.
If the retained document changed after inspection, the mutation fails instead
of overwriting it. List and receipt commands default to offset 0 and limit 100;
the maximum page is 200.

## Console HTTP surface

Read operations:

```text
GET /api/v1/memory/indexes
GET /api/v1/memory/documents
GET /api/v1/memory/documents/{document_id}
GET /api/v1/memory/documents/{document_id}/export
GET /api/v1/memory/receipts
```

Mutation operations:

```text
POST /api/v1/memory/indexes
POST /api/v1/memory/documents/{document_id}/correct
POST /api/v1/memory/documents/{document_id}/delete
POST /api/v1/memory/grants/{grant_id}/expire
```

A correction body contains exactly `request_id`, `expected_content_sha256`,
`replacement_content`, `replacement_content_sha256`, and `confirmed`. A deletion
contains exactly `request_id`, `expected_content_sha256`, and `confirmed`. Manual
expiry contains exactly `request_id` and `confirmed`. Unknown fields fail closed.
The request ID may be omitted by the Console client, but callers that need safe
retry across an interrupted response should supply and retain one.

## Receipts and removal

Correction receipts retain the previous and resulting content digests. Deletion
and manual-expiry receipts retain a tombstone digest and the affected document
IDs after payload removal. Receipts are encrypted owner records and cannot be
used to recover removed content. Manual expiry may remove a grant that has no
documents left, producing an empty affected-document list.

## Installed qualification

Run:

```bash
PYTHONPATH=src .verification-venv/bin/python -m tools.run_phase20_management_exit
```

The gate builds and signs a seven-component release, installs it privately, and
uses only installed FAM_OS code. It exercises Shell and Console inspection,
export, correction, deletion, grant expiry, explicit-confirmation denial,
restart persistence, exact request replay, encrypted-at-rest nonce absence,
healthy diagnosis, and complete removal. Raw evidence is written to
`artifacts/memory/phase20.4-memory-management.json`.
