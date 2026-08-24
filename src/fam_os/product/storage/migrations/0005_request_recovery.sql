CREATE TABLE request_recovery(
 request_id TEXT PRIMARY KEY REFERENCES requests(request_id) ON DELETE CASCADE,
 work_kind TEXT NOT NULL,
 state TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;
