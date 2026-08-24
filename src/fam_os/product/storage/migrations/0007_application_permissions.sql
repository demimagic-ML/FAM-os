CREATE TABLE application_permissions(
    grant_id TEXT PRIMARY KEY NOT NULL,
    subject_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('active','revoked')),
    payload_ciphertext TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX application_permissions_subject_idx
ON application_permissions(subject_id, state);
