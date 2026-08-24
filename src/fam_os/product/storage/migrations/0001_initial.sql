CREATE TABLE requests(
 request_id TEXT PRIMARY KEY,
 payload_ciphertext TEXT NOT NULL,
 state TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE plans(
 plan_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
 revision INTEGER NOT NULL CHECK(revision >= 0),
 state TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE events(
 event_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
 plan_id TEXT REFERENCES plans(plan_id) ON DELETE CASCADE,
 sequence INTEGER NOT NULL CHECK(sequence >= 0),
 kind TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL,
 UNIQUE(plan_id, sequence)
) STRICT;

CREATE TABLE authorities(
 authority_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
 scope_ciphertext TEXT NOT NULL,
 state TEXT NOT NULL,
 issued_at TEXT NOT NULL,
 expires_at TEXT
) STRICT;

CREATE TABLE decisions(
 decision_id TEXT PRIMARY KEY,
 plan_id TEXT NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
 authority_id TEXT REFERENCES authorities(authority_id),
 kind TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 decided_at TEXT NOT NULL
) STRICT;

CREATE TABLE actions(
 action_id TEXT PRIMARY KEY,
 plan_id TEXT NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
 capability_id TEXT NOT NULL,
 state TEXT NOT NULL,
 idempotency_key TEXT NOT NULL UNIQUE,
 payload_ciphertext TEXT NOT NULL,
 postcondition_ciphertext TEXT,
 updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE evidence_refs(
 evidence_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
 plan_id TEXT REFERENCES plans(plan_id) ON DELETE CASCADE,
 action_id TEXT REFERENCES actions(action_id) ON DELETE SET NULL,
 kind TEXT NOT NULL,
 reference TEXT NOT NULL,
 sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
 recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE expert_state(
 expert_id TEXT PRIMARY KEY,
 package_ref TEXT NOT NULL,
 runtime_binding_ref TEXT,
 state TEXT NOT NULL,
 details_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE connector_state(
 connector_id TEXT PRIMARY KEY,
 instance_id TEXT,
 state TEXT NOT NULL,
 capability_digest TEXT,
 details_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE adaptation_metadata(
 record_id TEXT PRIMARY KEY,
 kind TEXT NOT NULL,
 feature_ciphertext TEXT NOT NULL,
 verified_evidence_id TEXT REFERENCES evidence_refs(evidence_id) ON DELETE SET NULL,
 updated_at TEXT NOT NULL
) STRICT;

CREATE INDEX plans_request_idx ON plans(request_id);
CREATE INDEX events_request_sequence_idx ON events(request_id, sequence);
CREATE INDEX actions_plan_idx ON actions(plan_id);
CREATE INDEX evidence_request_idx ON evidence_refs(request_id);
