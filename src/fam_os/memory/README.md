# Memory ownership

Owns permissioned local records, retrieval policy, provenance, retention, inspection, deletion, and reset behavior.

No memory source is globally available by default. Core passes only authorized context to an expert.

`MemoryRecordManifest` defines `fam.memory.record/v1alpha1` metadata for content integrity, owner/purpose scope, application/workspace/session scope, provenance lineage, sensitivity, retention, and expiry. It contains neither record content nor a database locator and does not grant retrieval authority. See `docs/protocols/MANIFEST_CONTRACTS.md` and ADR 0016.
