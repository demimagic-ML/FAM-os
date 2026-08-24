CREATE TABLE factory_training_resource_snapshots (
    owner_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    snapshot_sha256 TEXT NOT NULL CHECK (length(snapshot_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, snapshot_id),
    UNIQUE (owner_id, snapshot_sha256)
) STRICT;

CREATE TABLE factory_training_admission_decisions (
    owner_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    snapshot_sha256 TEXT NOT NULL,
    admitted INTEGER NOT NULL CHECK (admitted IN (0, 1)),
    decision_sha256 TEXT NOT NULL CHECK (length(decision_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, decision_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_training_approvals(owner_id, approval_id),
    FOREIGN KEY (owner_id, snapshot_sha256)
        REFERENCES factory_training_resource_snapshots(owner_id, snapshot_sha256)
) STRICT;
