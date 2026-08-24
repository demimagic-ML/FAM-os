CREATE TABLE useful_automation_runs(
 run_id TEXT PRIMARY KEY,
 automation_id TEXT NOT NULL REFERENCES useful_automations(automation_id) ON DELETE CASCADE,
 status TEXT NOT NULL,
 started_at TEXT NOT NULL,
 completed_at TEXT,
 task_id TEXT REFERENCES useful_tasks(task_id),
 error TEXT
) STRICT;

CREATE TABLE useful_notifications(
 notification_id TEXT PRIMARY KEY,
 kind TEXT NOT NULL,
 title TEXT NOT NULL,
 message TEXT NOT NULL,
 task_id TEXT REFERENCES useful_tasks(task_id),
 created_at TEXT NOT NULL,
 read_at TEXT
) STRICT;

CREATE INDEX useful_automation_runs_automation_idx ON useful_automation_runs(automation_id,started_at DESC);
CREATE INDEX useful_notifications_unread_idx ON useful_notifications(read_at,created_at DESC);
