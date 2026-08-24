CREATE TABLE factory_conversion_environments (
    owner_id TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    environment_id TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, manifest_sha256)
) STRICT;

CREATE TABLE factory_conversion_approvals (
    owner_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    one_use_conversion_id TEXT NOT NULL,
    environment_sha256 TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    consumed INTEGER NOT NULL CHECK (consumed IN (0, 1)),
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, approval_id),
    UNIQUE (owner_id, one_use_conversion_id),
    FOREIGN KEY (owner_id, decision_id)
        REFERENCES factory_evaluation_decisions(owner_id, decision_id),
    FOREIGN KEY (owner_id, environment_sha256)
        REFERENCES factory_conversion_environments(owner_id, manifest_sha256)
) STRICT;

CREATE TRIGGER factory_conversion_requires_promotable_decision
BEFORE INSERT ON factory_conversion_approvals
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM factory_evaluation_decisions decision
    WHERE decision.owner_id = NEW.owner_id
      AND decision.decision_id = NEW.decision_id
      AND decision.evaluation_id = NEW.evaluation_id
      AND decision.promotable = 1
)
BEGIN
    SELECT RAISE(ABORT, 'conversion requires a signed promotable decision');
END;

CREATE TABLE factory_conversion_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    conversion_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed', 'cancelled')),
    receipt_sha256 TEXT NOT NULL CHECK (length(receipt_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    UNIQUE (owner_id, approval_id),
    UNIQUE (owner_id, conversion_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_conversion_approvals(owner_id, approval_id)
) STRICT;

CREATE INDEX factory_conversion_approvals_by_state
ON factory_conversion_approvals(owner_id, active, consumed, expires_at, approval_id);
