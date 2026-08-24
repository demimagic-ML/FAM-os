CREATE TABLE fabric_peer_enrollments (
    enrollment_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN ('active', 'revoked')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    payload_ciphertext TEXT NOT NULL,
    enrolled_at TEXT NOT NULL,
    revoked_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((state = 'active' AND revoked_at IS NULL) OR
           (state = 'revoked' AND revoked_at IS NOT NULL))
) STRICT;

CREATE INDEX fabric_peer_enrollments_by_state
ON fabric_peer_enrollments(state, enrollment_id);
