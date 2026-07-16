"""Verified failure clustering and missing-capability discovery."""

from dataclasses import dataclass

EXPERT_DISCOVERY_CONTRACT_VERSION = "fam.factory.discovery/v1alpha1"


@dataclass(frozen=True, slots=True)
class FailureTrace:
    trace_id: str
    capability_id: str
    failed_requirement_id: str
    verifier_id: str
    evidence_sha256: str
    independently_verified: bool

    def __post_init__(self) -> None:
        if not self.independently_verified or len(self.evidence_sha256) != 64:
            raise ValueError("factory failure traces require verified evidence")


@dataclass(frozen=True, slots=True)
class FailureTraceCluster:
    cluster_id: str
    capability_id: str
    failed_requirement_id: str
    trace_ids: tuple[str, ...]
    evidence_sha256s: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MissingCapabilityProposal:
    proposal_id: str
    capability_id: str
    cluster_id: str
    observation_count: int
    training_authorized: bool = False
    contract_version: str = EXPERT_DISCOVERY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.training_authorized:
            raise ValueError("failure discovery cannot authorize training")


def cluster_failures(traces, minimum_observations=2):
    groups = {}
    for trace in traces:
        groups.setdefault((trace.capability_id, trace.failed_requirement_id), []).append(trace)
    clusters, proposals = [], []
    for index, (key, values) in enumerate(sorted(groups.items()), 1):
        cluster = FailureTraceCluster(
            f"cluster-{index}", key[0], key[1], tuple(item.trace_id for item in values),
            tuple(item.evidence_sha256 for item in values),
        )
        clusters.append(cluster)
        if len(values) >= minimum_observations:
            proposals.append(MissingCapabilityProposal(
                f"missing-{index}", key[0], cluster.cluster_id, len(values),
            ))
    return tuple(clusters), tuple(proposals)
