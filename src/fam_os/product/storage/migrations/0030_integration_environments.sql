CREATE TABLE integration_environments (
    environment_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active','failed','cleaned')),
    plan_ciphertext TEXT NOT NULL,
    candidate_ciphertext TEXT NOT NULL,
    start_result_ciphertext TEXT NOT NULL,
    latest_receipt_ciphertext TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX integration_environments_owner_state
ON integration_environments(owner_id,state,updated_at);

CREATE TABLE integration_environment_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    environment_id TEXT NOT NULL,
    event_kind TEXT NOT NULL CHECK (event_kind IN ('started','cleaned','reconciled')),
    receipt_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(environment_id) REFERENCES integration_environments(environment_id)
) STRICT;

CREATE INDEX integration_environment_events_environment
ON integration_environment_events(environment_id,sequence);
