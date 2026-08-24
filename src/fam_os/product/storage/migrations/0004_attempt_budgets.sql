CREATE TABLE global_attempt_budgets(
 plan_instance_id TEXT PRIMARY KEY,
 payload_ciphertext TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE TABLE attempt_budget_reservations(
 reservation_id TEXT PRIMARY KEY,
 plan_instance_id TEXT NOT NULL REFERENCES global_attempt_budgets(plan_instance_id) ON DELETE CASCADE,
 attempt_id TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL,
 reserved_tokens INTEGER NOT NULL CHECK(reserved_tokens > 0),
 reserved_wall_milliseconds INTEGER NOT NULL CHECK(reserved_wall_milliseconds > 0),
 payload_ciphertext TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE INDEX attempt_budget_plan_idx ON attempt_budget_reservations(plan_instance_id);
