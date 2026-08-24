CREATE TABLE factory_failure_traces (
    owner_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    verification_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    failed_requirement_id TEXT NOT NULL,
    verifier_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    PRIMARY KEY (owner_id, trace_id),
    UNIQUE (owner_id, verification_id)
) STRICT;

CREATE INDEX factory_failure_traces_by_family
ON factory_failure_traces(
    owner_id, family_id, observed_at, trace_id
);

CREATE TABLE factory_failure_clusters (
    owner_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    observation_count INTEGER NOT NULL CHECK (observation_count >= 1),
    last_observed_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    PRIMARY KEY (owner_id, cluster_id)
) STRICT;

CREATE INDEX factory_failure_clusters_by_family
ON factory_failure_clusters(
    owner_id, family_id, observation_count, last_observed_at, cluster_id
);

CREATE TABLE factory_capability_proposals (
    owner_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    observation_count INTEGER NOT NULL CHECK (observation_count >= 2),
    proposed_at TEXT NOT NULL,
    payload_ciphertext TEXT NOT NULL,
    PRIMARY KEY (owner_id, proposal_id),
    FOREIGN KEY (owner_id, cluster_id)
        REFERENCES factory_failure_clusters(owner_id, cluster_id)
) STRICT;

CREATE INDEX factory_capability_proposals_by_family
ON factory_capability_proposals(
    owner_id, family_id, observation_count, proposed_at, proposal_id
);
