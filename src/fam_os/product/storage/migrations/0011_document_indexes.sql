CREATE TABLE document_index_grants(
    grant_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX document_index_grants_owner_expiry
ON document_index_grants(owner_id, expires_at);

CREATE TABLE document_index_documents(
    document_id TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL REFERENCES document_index_grants(grant_id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX document_index_documents_grant
ON document_index_documents(grant_id, document_id);

CREATE TABLE document_index_chunks(
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES document_index_documents(document_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
    payload_ciphertext TEXT NOT NULL,
    UNIQUE(document_id, ordinal)
) STRICT;

CREATE INDEX document_index_chunks_document
ON document_index_chunks(document_id, ordinal);
