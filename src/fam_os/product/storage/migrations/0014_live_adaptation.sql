CREATE TABLE live_adaptation_snapshots(
 owner_id TEXT NOT NULL,
 snapshot_id TEXT NOT NULL,
 workflow_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(owner_id,snapshot_id)
) STRICT;

CREATE INDEX live_adaptation_workflow_idx
ON live_adaptation_snapshots(owner_id,workflow_id,recorded_at,snapshot_id);

CREATE TABLE model_prewarm_receipts(
 owner_id TEXT NOT NULL,
 receipt_id TEXT NOT NULL,
 snapshot_id TEXT NOT NULL,
 payload_ciphertext TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 PRIMARY KEY(owner_id,receipt_id),
 FOREIGN KEY(owner_id,snapshot_id)
  REFERENCES live_adaptation_snapshots(owner_id,snapshot_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX model_prewarm_snapshot_idx
ON model_prewarm_receipts(owner_id,snapshot_id,recorded_at,receipt_id);
