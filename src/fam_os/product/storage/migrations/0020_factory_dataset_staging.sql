CREATE TABLE factory_capture_grants (
    owner_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    expires_at TEXT NOT NULL,
    maximum_source_bytes INTEGER NOT NULL CHECK (maximum_source_bytes >= 1),
    maximum_examples INTEGER NOT NULL CHECK (maximum_examples >= 1),
    payload_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, grant_id),
    FOREIGN KEY (owner_id, proposal_id)
        REFERENCES factory_capability_proposals(owner_id, proposal_id)
) STRICT;

CREATE TABLE factory_capture_revocations (
    owner_id TEXT NOT NULL,
    receipt_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, receipt_id),
    FOREIGN KEY (owner_id, grant_id)
        REFERENCES factory_capture_grants(owner_id, grant_id)
) STRICT;

CREATE TABLE factory_dataset_sources (
    owner_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    source_family_id TEXT NOT NULL,
    partition TEXT NOT NULL CHECK (partition IN ('train', 'validation', 'held_out')),
    content_bytes INTEGER NOT NULL CHECK (content_bytes >= 1),
    payload_ciphertext TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, source_id),
    FOREIGN KEY (owner_id, grant_id)
        REFERENCES factory_capture_grants(owner_id, grant_id)
) STRICT;

CREATE INDEX factory_dataset_sources_by_grant
ON factory_dataset_sources(owner_id, grant_id, partition, captured_at, source_id);

CREATE TABLE factory_synthetic_examples (
    owner_id TEXT NOT NULL,
    example_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_family_id TEXT NOT NULL,
    partition TEXT NOT NULL CHECK (partition IN ('train', 'validation')),
    content_bytes INTEGER NOT NULL CHECK (content_bytes >= 1),
    payload_ciphertext TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, example_id),
    FOREIGN KEY (owner_id, grant_id)
        REFERENCES factory_capture_grants(owner_id, grant_id),
    FOREIGN KEY (owner_id, source_id)
        REFERENCES factory_dataset_sources(owner_id, source_id)
) STRICT;

CREATE INDEX factory_synthetic_examples_by_grant
ON factory_synthetic_examples(owner_id, grant_id, partition, generated_at, example_id);

CREATE TABLE factory_synthetic_reviews (
    owner_id TEXT NOT NULL,
    review_id TEXT NOT NULL,
    example_id TEXT NOT NULL,
    accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    payload_ciphertext TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, review_id),
    UNIQUE (owner_id, example_id),
    FOREIGN KEY (owner_id, example_id)
        REFERENCES factory_synthetic_examples(owner_id, example_id)
) STRICT;
