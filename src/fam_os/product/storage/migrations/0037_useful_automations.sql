CREATE TABLE useful_automations(
 automation_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 request_json TEXT NOT NULL,
 trigger_json TEXT NOT NULL,
 condition_json TEXT NOT NULL,
 run_mode TEXT NOT NULL CHECK(run_mode IN ('single','restart','queued','parallel')),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 trigger_state_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 last_run_at TEXT,
 last_task_id TEXT,
 last_status TEXT
) STRICT;

CREATE INDEX useful_automations_enabled_idx ON useful_automations(enabled,updated_at);
