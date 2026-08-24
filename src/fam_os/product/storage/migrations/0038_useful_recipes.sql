CREATE TABLE useful_recipes(
 recipe_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 description TEXT NOT NULL,
 request_template_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 source_task_id TEXT REFERENCES useful_tasks(task_id)
) STRICT;

CREATE INDEX useful_recipes_updated_idx ON useful_recipes(updated_at DESC);
