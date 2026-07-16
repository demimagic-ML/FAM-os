# Memory record lifecycle

Phase 10.1 defines one versioned identity chain for local memory:

- `MemoryRecordManifest` binds record kind, creation time, content schema/media type/size/digest, sensitivity, and retention policy.
- `MemoryScope` binds an owner and one or more explicit purposes, with optional application, workspace, and session limits.
- `MemoryProvenance` binds source kind, source ID, creator, capture time, and parent records for derived memory.
- `MemoryExpiryEvaluation` deterministically derives active or expired state from timezone-aware expiry and evaluation times. Purged-by-expiry cannot precede expiry.
- `MemoryDeletionRequest` binds record, owner, actor, time, and reason.
- `MemoryDeletionReceipt` is valid only after payload removal and records the prior content digest plus a non-content tombstone digest.

Deletion receipts prove what was removed without retaining the deleted payload. They do not authorize deletion: owner/scope authorization and storage mutation are implemented in later Phase 10 services. All public roots have strict schemas and round-trip fixtures.
