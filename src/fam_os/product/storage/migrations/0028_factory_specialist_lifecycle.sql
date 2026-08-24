CREATE TABLE factory_specialist_lifecycle_requests (
    owner_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (
        action IN ('manual_rollback','forced_regression_rollback','retire')
    ),
    release_id TEXT NOT NULL,
    target_release_id TEXT,
    expected_lifecycle_revision INTEGER NOT NULL CHECK (
        expected_lifecycle_revision >= 0
    ),
    status TEXT NOT NULL CHECK (status IN ('pending','completed')),
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, request_id),
    UNIQUE (owner_id, request_sha256)
) STRICT;

CREATE TABLE factory_specialist_lifecycle_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (
        action IN ('manual_rollback','forced_regression_rollback','retire')
    ),
    release_id TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL CHECK (length(receipt_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    UNIQUE (owner_id, request_id),
    UNIQUE (owner_id, receipt_sha256),
    FOREIGN KEY (owner_id, request_id) REFERENCES
        factory_specialist_lifecycle_requests(owner_id, request_id)
) STRICT;

