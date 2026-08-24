# ADR 0126: Persistent document indexing requires expiring path grants

**Status:** Accepted  
**Date:** 2026-07-17

## Context

The Phase 10 document index could verify source digests and memory scope, but it
used a standalone SQLite file, exposed positional rows, had no folder authority
contract, and was not reachable from the installed product. Connecting that
implementation directly would permit persistent storage without a time bound
and would make safe filesystem traversal, encryption, and user intent implicit.

Persistent project knowledge is materially different from process-only session
memory. It survives restart, can contain private files, and must never become a
general home-directory crawler.

## Decision

FAM_OS indexes local documents only after an authenticated Console mutation with
`confirmed=true`. The server—not request JSON—assigns the owner, approver, grant
identity, embedding model, exact local model-manifest digest, approval instant,
and absolute expiry. A grant binds one absolute file or folder, recursion,
purpose/application/workspace scope, a safe text-extension subset, and hard
file, per-file byte, total-byte, and lifetime limits. The maximum lifetime is 90
days.

Traversal opens every directory component descriptor-relatively with
`O_NOFOLLOW`; files are opened relative to held directory descriptors and must
be owner-controlled, regular, single-link, stable while read, bounded, and
strict UTF-8. Symlinks, devices, hard links, unsupported extensions, and changed
files are not indexed. Folder enumeration has a derived scan bound and stable
ordering. Chunks exactly reconstruct the approved bytes and are embedded by the
signed release's enabled embedding expert.

The main owner-private ProductDatabase stores grants, approvals, content, and
embeddings as context-bound AEAD contract ciphertext. Only lookup identities,
digests, expiry, and relationship keys remain queryable. Expired grants are
hidden by policy and cascade-delete their documents and chunks at startup,
access, and from a supervised expiry worker. Indexing is atomic: failure removes
the grant and any already-created child records.

Phase 20.2 exposes authenticated create/list controls. Retrieval injection and
exact citations belong to 20.3; complete inspect/correct/export/expire/delete
surfaces and durable management receipts belong to 20.4.

## Consequences

- Persistent indexing is absent by default and cannot start from model output.
- A client cannot widen ownership, model provenance, expiry, or filesystem
  scope by adding JSON fields; unknown fields fail closed.
- Restart preserves only unexpired, explicitly granted indexes.
- Expiry removes payloads by foreign-key cascade without decrypting them.
- File paths are shown back only to the authenticated owner and remain encrypted
  at rest.
- Phase 20.3 must consume this repository through the typed scope and expiry
  boundary rather than issuing direct SQLite queries.
