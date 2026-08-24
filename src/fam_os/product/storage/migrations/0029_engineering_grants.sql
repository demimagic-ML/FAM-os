CREATE TABLE engineering_grants (
    grant_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active','revoked','consumed')),
    reconfirmation_required INTEGER NOT NULL CHECK (reconfirmation_required IN (0,1)),
    grant_ciphertext TEXT NOT NULL,
    approval_ciphertext TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX engineering_grants_principal_state
ON engineering_grants(principal_id,state,reconfirmation_required);

CREATE TABLE engineering_authorization_audit (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL UNIQUE,
    grant_id TEXT NOT NULL,
    authority TEXT NOT NULL,
    allowed INTEGER NOT NULL CHECK (allowed IN (0,1)),
    decision_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;
