CREATE TABLE useful_task_steps(
 task_id TEXT NOT NULL REFERENCES useful_tasks(task_id) ON DELETE CASCADE,
 step_id TEXT NOT NULL,
 tool_id TEXT NOT NULL,
 arguments_json TEXT NOT NULL,
 attempt INTEGER NOT NULL CHECK(attempt BETWEEN 1 AND 3),
 status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
 output_json TEXT,
 error TEXT,
 started_at TEXT NOT NULL,
 completed_at TEXT,
 PRIMARY KEY(task_id,step_id,attempt)
) STRICT;

CREATE INDEX useful_task_steps_task_idx ON useful_task_steps(task_id,started_at);
