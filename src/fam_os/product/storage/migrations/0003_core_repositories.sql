CREATE TABLE core_replay(
 reservation_kind TEXT NOT NULL,
 reservation_id TEXT NOT NULL,
 reserved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(reservation_kind, reservation_id)
) STRICT;

CREATE TABLE authority_grants(
 authority_ref TEXT PRIMARY KEY,
 payload_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE TABLE plan_snapshots(
 instance_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL,
 plan_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision >= 0),
 payload_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 UNIQUE(request_id, plan_id)
) STRICT;

CREATE TABLE core_policies(
 policy_kind TEXT NOT NULL,
 policy_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(policy_kind, policy_id)
) STRICT;

CREATE TABLE final_evidence(
 evidence_kind TEXT NOT NULL,
 evidence_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(evidence_kind, evidence_id)
) STRICT;
