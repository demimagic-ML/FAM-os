CREATE TABLE agent_goal_ledgers(
  thread_id TEXT PRIMARY KEY,
  original_request TEXT NOT NULL,
  accepted_plan TEXT NOT NULL DEFAULT '',
  current_objective TEXT NOT NULL,
  completed_objectives_json TEXT NOT NULL DEFAULT '[]',
  unresolved_items_json TEXT NOT NULL DEFAULT '[]',
  context_generation INTEGER NOT NULL DEFAULT 0,
  compaction_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(thread_id) REFERENCES agent_threads(thread_id) ON DELETE CASCADE
);

CREATE TABLE agent_execution_checkpoints(
  checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  graph_node TEXT NOT NULL CHECK(graph_node IN (
    'prepare','infer','execute','observe','recover','verify','complete','failed'
  )),
  model_step INTEGER NOT NULL,
  phase TEXT NOT NULL,
  state_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(turn_id) REFERENCES agent_turns(turn_id) ON DELETE CASCADE,
  UNIQUE(turn_id,sequence)
);

CREATE INDEX agent_execution_checkpoint_turn_idx
  ON agent_execution_checkpoints(turn_id,sequence);
CREATE INDEX agent_execution_checkpoint_thread_idx
  ON agent_execution_checkpoints(thread_id,checkpoint_id);
