ALTER TABLE final_evidence ADD COLUMN request_id TEXT;

CREATE INDEX final_evidence_request_idx
ON final_evidence(evidence_kind, request_id, recorded_at);

CREATE TABLE terminal_results(
 request_id TEXT PRIMARY KEY REFERENCES requests(request_id) ON DELETE CASCADE,
 owner_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('completed','verified','withheld','failed')),
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE TABLE verified_learning_outcomes(
 learning_id TEXT PRIMARY KEY,
 owner_id TEXT NOT NULL,
 acceptance_evidence_kind TEXT NOT NULL DEFAULT 'acceptance'
  CHECK(acceptance_evidence_kind='acceptance'),
 acceptance_evidence_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(owner_id, acceptance_evidence_id),
 FOREIGN KEY(acceptance_evidence_kind,acceptance_evidence_id)
  REFERENCES final_evidence(evidence_kind,evidence_id) ON DELETE RESTRICT
) STRICT;
