CREATE TABLE factory_training_environments (
    owner_id TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    environment_id TEXT NOT NULL,
    qlora_compatible INTEGER NOT NULL CHECK (qlora_compatible IN (0, 1)),
    payload_ciphertext TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, manifest_sha256)
) STRICT;

CREATE TABLE factory_training_jobs (
    owner_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    environment_sha256 TEXT NOT NULL,
    job_sha256 TEXT NOT NULL CHECK (length(job_sha256) = 64),
    state TEXT NOT NULL CHECK (state IN ('admitted', 'running', 'terminal')),
    payload_ciphertext TEXT NOT NULL,
    admitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, job_id),
    UNIQUE (owner_id, approval_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_training_approvals(owner_id, approval_id),
    FOREIGN KEY (owner_id, dataset_id)
        REFERENCES factory_sealed_datasets(owner_id, dataset_id),
    FOREIGN KEY (owner_id, environment_sha256)
        REFERENCES factory_training_environments(owner_id, manifest_sha256)
) STRICT;

CREATE TABLE factory_training_terminal_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('completed', 'failed', 'cancelled', 'revoked', 'resource_stopped')
    ),
    receipt_sha256 TEXT NOT NULL CHECK (length(receipt_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    UNIQUE (owner_id, job_id),
    FOREIGN KEY (owner_id, job_id)
        REFERENCES factory_training_jobs(owner_id, job_id)
) STRICT;

CREATE INDEX factory_training_jobs_by_state
ON factory_training_jobs(owner_id, state, admitted_at, job_id);
