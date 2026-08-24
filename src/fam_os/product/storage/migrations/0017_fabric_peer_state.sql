CREATE TABLE fabric_peer_capabilities (
    enrollment_id TEXT NOT NULL,
    declaration_id TEXT NOT NULL,
    expert_id_hash TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (enrollment_id, declaration_id),
    UNIQUE (enrollment_id, expert_id_hash),
    FOREIGN KEY (enrollment_id) REFERENCES fabric_peer_enrollments(enrollment_id)
) STRICT;

CREATE INDEX fabric_peer_capabilities_by_enrollment
ON fabric_peer_capabilities(enrollment_id, expires_at, declaration_id);

CREATE TABLE fabric_peer_performance (
    enrollment_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (enrollment_id, observation_id),
    FOREIGN KEY (enrollment_id) REFERENCES fabric_peer_enrollments(enrollment_id)
) STRICT;

CREATE INDEX fabric_peer_performance_by_enrollment
ON fabric_peer_performance(enrollment_id, observed_at DESC, observation_id DESC);

CREATE TABLE fabric_peer_privacy_policies (
    enrollment_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    payload_ciphertext TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (enrollment_id) REFERENCES fabric_peer_enrollments(enrollment_id)
) STRICT;

CREATE TABLE fabric_peer_management_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('revoke', 'set_privacy')),
    enrollment_id TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    UNIQUE (owner_id, request_id),
    FOREIGN KEY (enrollment_id) REFERENCES fabric_peer_enrollments(enrollment_id)
) STRICT;

CREATE INDEX fabric_peer_management_receipts_order
ON fabric_peer_management_receipts(owner_id, recorded_at, receipt_id);
