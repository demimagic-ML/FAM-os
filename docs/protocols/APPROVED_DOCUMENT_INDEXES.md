# Approved document indexes

Phase 10.3 adds durable local document retrieval with no implicit ingestion path.

`DocumentIndexApproval` binds document ID, source locator and SHA-256, owner/purpose/application/workspace/session scope, approver/time, and exact embedding model artifact. Indexing rejects content whose digest differs from approval and rejects chunk sets that do not exactly reconstruct the approved content.

SQLite persists approvals, source evidence, chunks, and embeddings. Retrieval filters rows through the exact memory access context before embedding the query or scoring any content. A request cannot mix incompatible embedding model spaces. Results retain document/chunk IDs, source locator/digest, content, and cosine score.

The workstation proof indexed two approved chunks with the installed digest-bound Nomic model. The hardware query returned chunk 0; a different owner received zero hits. Durable encryption is added in Phase 10.6, so this phase does not yet approve sensitive production persistence.
