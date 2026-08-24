CREATE TABLE adaptation_control_state(
 owner_id TEXT PRIMARY KEY,
 revision INTEGER NOT NULL CHECK(revision >= 0),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 payload_ciphertext TEXT NOT NULL,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE TABLE adaptation_control_receipts(
 owner_id TEXT NOT NULL,
 receipt_id TEXT NOT NULL,
 request_id TEXT NOT NULL,
 operation TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(owner_id,receipt_id),
 UNIQUE(owner_id,request_id)
) STRICT;

CREATE INDEX adaptation_control_receipt_idx
ON adaptation_control_receipts(owner_id,recorded_at,receipt_id);

CREATE TABLE adaptation_inference_observations(
 owner_id TEXT NOT NULL,
 observation_id TEXT NOT NULL,
 request_id TEXT NOT NULL,
 snapshot_id TEXT NOT NULL,
 workflow_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(owner_id,observation_id),
 FOREIGN KEY(owner_id,snapshot_id)
  REFERENCES live_adaptation_snapshots(owner_id,snapshot_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX adaptation_inference_request_idx
ON adaptation_inference_observations(owner_id,request_id,recorded_at,observation_id);

CREATE TABLE adaptation_health_samples(
 owner_id TEXT NOT NULL,
 sample_id TEXT NOT NULL,
 observation_id TEXT NOT NULL,
 snapshot_id TEXT NOT NULL,
 workflow_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(owner_id,sample_id),
 UNIQUE(owner_id,observation_id),
 FOREIGN KEY(owner_id,snapshot_id)
  REFERENCES live_adaptation_snapshots(owner_id,snapshot_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX adaptation_health_snapshot_idx
ON adaptation_health_samples(owner_id,snapshot_id,recorded_at,sample_id);

CREATE TABLE adaptation_drift_reports(
 owner_id TEXT NOT NULL,
 report_id TEXT NOT NULL,
 workflow_id TEXT NOT NULL,
 baseline_snapshot_id TEXT NOT NULL,
 candidate_snapshot_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(owner_id,report_id),
 FOREIGN KEY(owner_id,baseline_snapshot_id)
  REFERENCES live_adaptation_snapshots(owner_id,snapshot_id) ON DELETE CASCADE,
 FOREIGN KEY(owner_id,candidate_snapshot_id)
  REFERENCES live_adaptation_snapshots(owner_id,snapshot_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX adaptation_drift_workflow_idx
ON adaptation_drift_reports(owner_id,workflow_id,recorded_at,report_id);
