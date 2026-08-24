CREATE TABLE useful_tasks(
 task_id TEXT PRIMARY KEY,
 workflow_id TEXT NOT NULL,
 prompt TEXT NOT NULL,
 workspace_root TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('running','completed','failed','cancelled')),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 summary TEXT,
 error TEXT,
 continuation_json TEXT
) STRICT;

CREATE TABLE useful_artifacts(
 artifact_id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES useful_tasks(task_id) ON DELETE CASCADE,
 kind TEXT NOT NULL,
 path TEXT NOT NULL,
 media_type TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0)
) STRICT;

CREATE INDEX useful_tasks_updated_idx ON useful_tasks(updated_at DESC);
CREATE INDEX useful_artifacts_task_idx ON useful_artifacts(task_id);
