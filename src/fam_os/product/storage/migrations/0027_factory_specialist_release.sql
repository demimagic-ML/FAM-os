CREATE TABLE factory_specialist_release_lineages (
    owner_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    package_version TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    conversion_receipt_id TEXT NOT NULL,
    lineage_sha256 TEXT NOT NULL CHECK (length(lineage_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, release_id),
    UNIQUE (owner_id, package_id, package_version),
    FOREIGN KEY (owner_id, decision_id)
        REFERENCES factory_evaluation_decisions(owner_id, decision_id),
    FOREIGN KEY (owner_id, conversion_receipt_id)
        REFERENCES factory_conversion_receipts(owner_id, receipt_id)
) STRICT;

CREATE TABLE factory_specialist_package_receipts (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    package_version TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL CHECK (length(receipt_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    UNIQUE (owner_id, release_id),
    UNIQUE (owner_id, package_id, package_version),
    FOREIGN KEY (owner_id, release_id)
        REFERENCES factory_specialist_release_lineages(owner_id, release_id)
) STRICT;

CREATE TABLE factory_canary_approvals (
    owner_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    package_receipt_sha256 TEXT NOT NULL CHECK (length(package_receipt_sha256) = 64),
    one_use_canary_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    consumed INTEGER NOT NULL CHECK (consumed IN (0, 1)),
    expires_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, approval_id),
    UNIQUE (owner_id, one_use_canary_id)
) STRICT;

CREATE TRIGGER factory_canary_requires_installed_package
BEFORE INSERT ON factory_canary_approvals
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1 FROM factory_specialist_package_receipts package
    WHERE package.owner_id = NEW.owner_id
      AND package.receipt_sha256 = NEW.package_receipt_sha256
)
BEGIN
    SELECT RAISE(ABORT, 'canary requires a signed installed package');
END;

CREATE TABLE factory_canary_reports (
    owner_id TEXT NOT NULL,
    report_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    canary_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed', 'cancelled')),
    report_sha256 TEXT NOT NULL CHECK (length(report_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, report_id),
    UNIQUE (owner_id, approval_id),
    UNIQUE (owner_id, canary_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_canary_approvals(owner_id, approval_id)
) STRICT;

CREATE TABLE factory_activation_decisions (
    owner_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    canary_id TEXT NOT NULL,
    report_sha256 TEXT NOT NULL CHECK (length(report_sha256) = 64),
    activate INTEGER NOT NULL CHECK (activate IN (0, 1)),
    decision_sha256 TEXT NOT NULL CHECK (length(decision_sha256) = 64),
    payload_ciphertext TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, decision_id),
    UNIQUE (owner_id, approval_id),
    UNIQUE (owner_id, canary_id),
    FOREIGN KEY (owner_id, approval_id)
        REFERENCES factory_canary_approvals(owner_id, approval_id)
) STRICT;

CREATE INDEX factory_canary_approvals_by_state
ON factory_canary_approvals(owner_id, active, consumed, expires_at, approval_id);
