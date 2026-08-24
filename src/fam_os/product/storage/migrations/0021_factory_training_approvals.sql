CREATE TABLE factory_training_approvals (
    owner_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    sealed_dataset_id TEXT NOT NULL,
    one_use_job_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    consumed INTEGER NOT NULL CHECK (consumed IN (0, 1)),
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, approval_id),
    UNIQUE (owner_id, one_use_job_id),
    FOREIGN KEY (owner_id, proposal_id)
        REFERENCES factory_capability_proposals(owner_id, proposal_id)
) STRICT;

CREATE TABLE factory_training_approval_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('consume', 'revoke')),
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_training_approvals(owner_id, approval_id)
) STRICT;

CREATE INDEX factory_training_approvals_by_state
ON factory_training_approvals(owner_id, active, consumed, expires_at, approval_id);
