ALTER TABLE useful_tasks ADD COLUMN request_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE useful_tasks ADD COLUMN parent_task_id TEXT REFERENCES useful_tasks(task_id);
ALTER TABLE useful_tasks ADD COLUMN project_id TEXT;

CREATE INDEX useful_tasks_project_idx ON useful_tasks(project_id,updated_at DESC);
CREATE INDEX useful_tasks_parent_idx ON useful_tasks(parent_task_id);
