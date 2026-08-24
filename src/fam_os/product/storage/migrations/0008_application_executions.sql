CREATE TABLE application_executions(
    instance_id TEXT PRIMARY KEY NOT NULL,
    request_id TEXT NOT NULL UNIQUE REFERENCES requests(request_id) ON DELETE CASCADE,
    revision INTEGER NOT NULL CHECK(revision >= 0),
    state TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX application_executions_state_idx
ON application_executions(state, updated_at);
