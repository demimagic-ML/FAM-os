CREATE TABLE agent_thread_controls(
  control_id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id TEXT NOT NULL,
  control_kind TEXT NOT NULL CHECK(control_kind IN ('steer','cancel')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  consumed_at TEXT,
  FOREIGN KEY(thread_id) REFERENCES agent_threads(thread_id) ON DELETE CASCADE
);

CREATE INDEX agent_thread_control_pending_idx
  ON agent_thread_controls(thread_id,consumed_at,control_id);
