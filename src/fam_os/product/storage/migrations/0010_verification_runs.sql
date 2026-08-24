CREATE TABLE verification_declarations(
    declaration_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE verification_runs(
    verification_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('passed','failed','error')),
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(request_id, candidate_id)
) STRICT;

CREATE INDEX verification_runs_request_idx
ON verification_runs(request_id, created_at, verification_id);
