CREATE TABLE application_action_states(
    action_id TEXT PRIMARY KEY NOT NULL,
    plan_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    state TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_ciphertext TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX application_action_states_plan_idx
ON application_action_states(plan_id, state);
