CREATE TABLE factory_dataset_leakage_reports (
    owner_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    candidate_dataset_id TEXT NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
    report_sha256 TEXT NOT NULL CHECK (length(report_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, report_id),
    UNIQUE (owner_id, candidate_dataset_id)
) STRICT;

CREATE TABLE factory_sealed_datasets (
    owner_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    leakage_report_id TEXT NOT NULL,
    immutable INTEGER NOT NULL CHECK (immutable = 1),
    training_ready INTEGER NOT NULL CHECK (training_ready = 1),
    payload_ciphertext TEXT NOT NULL,
    sealed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, dataset_id),
    UNIQUE (owner_id, manifest_sha256),
    FOREIGN KEY (owner_id, proposal_id)
        REFERENCES factory_capability_proposals(owner_id, proposal_id),
    FOREIGN KEY (owner_id, grant_id)
        REFERENCES factory_capture_grants(owner_id, grant_id),
    FOREIGN KEY (owner_id, leakage_report_id)
        REFERENCES factory_dataset_leakage_reports(owner_id, report_id)
) STRICT;

CREATE TABLE factory_sealed_dataset_blobs (
    owner_id TEXT NOT NULL,
    blob_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    partition TEXT NOT NULL CHECK (partition IN ('train', 'validation', 'held_out')),
    plaintext_sha256 TEXT NOT NULL CHECK (length(plaintext_sha256) = 64),
    ciphertext_sha256 TEXT NOT NULL CHECK (length(ciphertext_sha256) = 64),
    relative_path TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, blob_id),
    UNIQUE (owner_id, dataset_id, partition),
    FOREIGN KEY (owner_id, dataset_id)
        REFERENCES factory_sealed_datasets(owner_id, dataset_id)
) STRICT;

CREATE INDEX factory_sealed_datasets_by_proposal
ON factory_sealed_datasets(owner_id, proposal_id, sealed_at, dataset_id);

CREATE TRIGGER factory_training_approval_requires_sealed_dataset
BEFORE INSERT ON factory_training_approvals
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM factory_sealed_datasets d
    WHERE d.owner_id = NEW.owner_id
      AND d.dataset_id = NEW.sealed_dataset_id
      AND d.proposal_id = NEW.proposal_id
      AND d.training_ready = 1
)
BEGIN
    SELECT RAISE(ABORT, 'training approval requires a sealed training-ready dataset');
END;
