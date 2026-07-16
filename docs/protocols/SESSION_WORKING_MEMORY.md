# Session and working memory

Phase 10.2 provides a bounded ephemeral store for `session` and `working` records.

Every write verifies exact byte size and SHA-256 content digest against the manifest. Duplicate IDs, unsupported record kinds, record-count overflow, and byte-capacity overflow fail closed. The store never silently evicts another task’s memory.

Every read and inspection requires `MemoryAccessContext`. Owner and purpose must match exactly; declared application, workspace, and session restrictions must also match. Expired records are hidden immediately and can be deterministically purged.

Deletion requires an owner-bound request. The store removes the bytes and updates capacity before it creates the deletion receipt. This store is intentionally process-ephemeral; durable approved document memory begins in Phase 10.3.
