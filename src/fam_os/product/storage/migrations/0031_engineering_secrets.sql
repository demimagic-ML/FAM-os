CREATE TABLE engineering_secrets (
    secret_ref TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    tool_key TEXT NOT NULL,
    consumer_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active','deleted')),
    generation INTEGER NOT NULL CHECK (generation > 0),
    value_ciphertext TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK ((state = 'active' AND value_ciphertext IS NOT NULL) OR
           (state = 'deleted' AND value_ciphertext IS NULL))
) STRICT;

CREATE TABLE engineering_secret_audit (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    secret_ref TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('provisioned','rotated','deleted')),
    generation INTEGER NOT NULL CHECK (generation > 0),
    occurred_at TEXT NOT NULL
) STRICT;

CREATE INDEX engineering_secret_audit_ref
ON engineering_secret_audit(secret_ref, sequence);
