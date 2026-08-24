CREATE TABLE useful_integrations(
 integration_id TEXT PRIMARY KEY,
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 configuration_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('ready','missing_runtime','error')),
 updated_at TEXT NOT NULL,
 last_checked_at TEXT,
 error TEXT
) STRICT;
