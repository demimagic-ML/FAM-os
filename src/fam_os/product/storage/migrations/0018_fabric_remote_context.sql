CREATE TABLE fabric_remote_context_disclosures (
    owner_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    enrollment_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('outbound', 'inbound')),
    content_sha256 TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, evidence_id),
    UNIQUE (owner_id, direction, request_id),
    FOREIGN KEY (enrollment_id) REFERENCES fabric_peer_enrollments(enrollment_id)
) STRICT;

CREATE INDEX fabric_remote_context_by_enrollment
ON fabric_remote_context_disclosures(owner_id, enrollment_id, recorded_at, evidence_id);
