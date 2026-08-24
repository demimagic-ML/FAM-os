CREATE TABLE factory_evaluation_approvals (
    owner_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    training_receipt_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    held_out_blob_id TEXT NOT NULL,
    one_use_evaluation_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    consumed INTEGER NOT NULL CHECK (consumed IN (0, 1)),
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, approval_id),
    UNIQUE (owner_id, one_use_evaluation_id),
    FOREIGN KEY (owner_id, proposal_id)
        REFERENCES factory_capability_proposals(owner_id, proposal_id),
    FOREIGN KEY (owner_id, training_receipt_id)
        REFERENCES factory_training_terminal_receipts(owner_id, receipt_id),
    FOREIGN KEY (owner_id, dataset_id)
        REFERENCES factory_sealed_datasets(owner_id, dataset_id),
    FOREIGN KEY (owner_id, held_out_blob_id)
        REFERENCES factory_sealed_dataset_blobs(owner_id, blob_id)
) STRICT;

CREATE TRIGGER factory_evaluation_approval_requires_completed_training
BEFORE INSERT ON factory_evaluation_approvals
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM factory_training_terminal_receipts terminal
    JOIN factory_training_jobs job
      ON job.owner_id = terminal.owner_id AND job.job_id = terminal.job_id
    JOIN factory_sealed_dataset_blobs held_out
      ON held_out.owner_id = job.owner_id
     AND held_out.dataset_id = job.dataset_id
     AND held_out.partition = 'held_out'
    WHERE terminal.owner_id = NEW.owner_id
      AND terminal.receipt_id = NEW.training_receipt_id
      AND terminal.status = 'completed'
      AND job.dataset_id = NEW.dataset_id
      AND held_out.blob_id = NEW.held_out_blob_id
)
BEGIN
    SELECT RAISE(ABORT, 'evaluation approval requires completed training and held-out data');
END;

CREATE TABLE factory_evaluation_runs (
    owner_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('claimed', 'running', 'terminal')),
    claimed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, evaluation_id),
    UNIQUE (owner_id, approval_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_evaluation_approvals(owner_id, approval_id)
) STRICT;

CREATE TABLE factory_held_out_access_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    held_out_blob_id TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL CHECK (length(receipt_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    UNIQUE (owner_id, evaluation_id),
    FOREIGN KEY (owner_id, evaluation_id)
        REFERENCES factory_evaluation_runs(owner_id, evaluation_id),
    FOREIGN KEY (owner_id, held_out_blob_id)
        REFERENCES factory_sealed_dataset_blobs(owner_id, blob_id)
) STRICT;

CREATE TABLE factory_evaluation_measurements (
    owner_id TEXT NOT NULL,
    measurement_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    kind TEXT NOT NULL CHECK (kind IN ('quality', 'safety', 'policy', 'unrelated')),
    measurement_sha256 TEXT NOT NULL CHECK (length(measurement_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    measured_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, measurement_id),
    UNIQUE (owner_id, evaluation_id, case_id),
    UNIQUE (owner_id, evaluation_id, ordinal),
    FOREIGN KEY (owner_id, evaluation_id)
        REFERENCES factory_evaluation_runs(owner_id, evaluation_id)
) STRICT;

CREATE TABLE factory_evaluation_reports (
    owner_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    report_sha256 TEXT NOT NULL CHECK (length(report_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, report_id),
    UNIQUE (owner_id, evaluation_id),
    FOREIGN KEY (owner_id, evaluation_id)
        REFERENCES factory_evaluation_runs(owner_id, evaluation_id)
) STRICT;

CREATE TABLE factory_evaluation_decisions (
    owner_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    report_sha256 TEXT NOT NULL CHECK (length(report_sha256) = 64),
    promotable INTEGER NOT NULL CHECK (promotable IN (0, 1)),
    decision_sha256 TEXT NOT NULL CHECK (length(decision_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, decision_id),
    UNIQUE (owner_id, evaluation_id),
    FOREIGN KEY (owner_id, evaluation_id)
        REFERENCES factory_evaluation_runs(owner_id, evaluation_id)
) STRICT;

CREATE INDEX factory_evaluation_approvals_by_state
ON factory_evaluation_approvals(
    owner_id, active, consumed, expires_at, approval_id
);

CREATE INDEX factory_evaluation_measurements_by_run
ON factory_evaluation_measurements(owner_id, evaluation_id, kind, ordinal);
