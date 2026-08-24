CREATE TABLE document_management_receipts(
    receipt_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    target_id TEXT NOT NULL,
    performed_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE UNIQUE INDEX document_management_receipts_owner_request
ON document_management_receipts(owner_id, request_id);

CREATE INDEX document_management_receipts_owner_time
ON document_management_receipts(owner_id, performed_at, receipt_id);

CREATE INDEX document_management_receipts_owner_target
ON document_management_receipts(owner_id, target_id, performed_at);
