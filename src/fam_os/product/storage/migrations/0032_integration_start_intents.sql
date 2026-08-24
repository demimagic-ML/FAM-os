CREATE TABLE integration_environment_start_intents (
    environment_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'starting','recovery_required','prelaunch_failed','recovered','committed'
    )),
    plan_ciphertext TEXT NOT NULL,
    candidate_ciphertext TEXT NOT NULL,
    permit_ciphertext TEXT,
    recovery_receipt_ciphertext TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX integration_start_intents_owner_state
ON integration_environment_start_intents(owner_id,state,updated_at);
