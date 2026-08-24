CREATE TABLE agent_threads(
  thread_id TEXT PRIMARY KEY,
  workspace_root TEXT NOT NULL,
  authority_profile TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE agent_turns(
  turn_id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  authority_profile TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('running','completed','failed','cancelled')),
  final_response TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY(thread_id) REFERENCES agent_threads(thread_id) ON DELETE CASCADE
);

CREATE TABLE agent_tool_events(
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  call_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  event_kind TEXT NOT NULL CHECK(event_kind IN ('call','result')),
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(turn_id) REFERENCES agent_turns(turn_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX agent_tool_event_identity_idx
  ON agent_tool_events(turn_id,call_id,event_kind);
CREATE INDEX agent_turn_thread_idx ON agent_turns(thread_id,created_at);
CREATE INDEX agent_tool_event_turn_idx ON agent_tool_events(turn_id,event_id);
