# ADR 0128: Persistent memory mutations are owner-controlled and receipt-bound

**Status:** Accepted  
**Date:** 2026-07-17

## Context

Phase 20.2 made approved document indexes durable and encrypted, and Phase 20.3
used them as authorized grounding sources. The installed product still needed a
complete owner path to inspect what was retained, correct an inaccurate retained
copy, export it, remove one document, expire a whole grant, and prove that a
destructive request completed after its payload was gone.

Retrieval scope is deliberately narrow, but it cannot also be the management
authority: a document approved only for MCP retrieval must not become invisible
or undeletable from the owner's Shell or Console. Mutations also cannot be
model-selected actions because correction and deletion change durable owner
state.

## Decision

Persistent memory management uses owner authority independently of retrieval
scope. An authenticated owner may list, inspect, and export all of that owner's
retained documents and receipts. Correction, document deletion, and manual grant
expiry require a typed request, an explicit confirmation value, and a durable
request ID. Document correction and deletion also require the current content
SHA-256, so stale concurrent state fails rather than overwriting newer content.

Correction changes only FAM_OS's retained copy. It preserves the grant, source
locator, provenance, and embedding-model identity, then chunks and re-embeds the
replacement. It does not edit the source file. A later approved re-index is a
separate operation and may replace that retained copy.

Each correction, deletion, or manual expiry and its owner-encrypted management
receipt commit in one SQLite transaction. Receipts outlive removed documents and
grants. A request ID is a durable idempotency key: replaying the same operation
and target returns its existing receipt, while reusing it for another operation
or target fails. Automatic natural expiry remains lifecycle cleanup and does not
pretend that a user requested a manual management mutation.

FAM Shell is a peer-authenticated owner client. FAM Console is a bearer-created,
same-origin session client whose mutations require Origin and CSRF validation.
Both call the same production management service. Shell pages are bounded and
its local frame limit is eight MiB so the valid one-MiB correction contract still
fits after worst-case JSON escaping. No model or expert receives direct access to
these controls.

## Consequences

- Retrieval restrictions never prevent an owner from seeing or removing memory.
- Stale corrections and deletions fail closed through digest comparison.
- Removing payloads does not remove the durable proof that removal occurred.
- Receipts are audit evidence, not a recovery copy of deleted content.
- Exact request replay is safe across process restart.
- Console and Shell share mutation semantics despite different local transports.
- A corrected retained copy can diverge from its source file until the user
  explicitly re-indexes that source.
