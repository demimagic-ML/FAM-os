"""Production content-free verified-failure discovery contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime


FACTORY_FAILURE_DISCOVERY_VERSION = "fam.factory.failure-discovery/v1alpha1"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


@dataclass(frozen=True, slots=True)
class VerifiedFailureTrace:
    trace_id: str
    verification_id: str
    request_id: str
    candidate_id: str
    capability_id: str
    failed_requirement_id: str
    verifier_id: str
    verifier_artifact_sha256: str
    candidate_sha256: str
    model_ref: str
    expert_tier: str
    release_id: str
    signer_key_id: str
    observed_at: datetime
    evidence_sha256: str
    independently_verified: bool = True
    training_authorized: bool = False
    contract_version: str = FACTORY_FAILURE_DISCOVERY_VERSION

    def __post_init__(self) -> None:
        for name in (
            "trace_id", "verification_id", "request_id", "candidate_id",
            "capability_id", "failed_requirement_id", "verifier_id",
            "model_ref", "expert_tier", "release_id", "signer_key_id",
        ):
            _identifier(getattr(self, name), name)
        for name in (
            "verifier_artifact_sha256", "candidate_sha256", "evidence_sha256",
        ):
            _sha256(getattr(self, name), name)
        _aware(self.observed_at, "observed_at")
        if not self.independently_verified:
            raise ValueError("factory traces require independent verification")
        if self.training_authorized:
            raise ValueError("failure discovery cannot authorize training")
        if self.contract_version != FACTORY_FAILURE_DISCOVERY_VERSION:
            raise ValueError("unsupported factory failure discovery version")
        if self.evidence_sha256 != failure_trace_digest(self):
            raise ValueError("failure trace evidence digest does not match")

    @property
    def family_id(self) -> str:
        return failure_family_id(
            self.capability_id, self.failed_requirement_id, self.verifier_id,
        )


@dataclass(frozen=True, slots=True)
class VerifiedFailureCluster:
    cluster_id: str
    family_id: str
    capability_id: str
    failed_requirement_id: str
    verifier_id: str
    trace_ids: tuple[str, ...]
    evidence_sha256s: tuple[str, ...]
    first_observed_at: datetime
    last_observed_at: datetime
    cluster_sha256: str
    contract_version: str = FACTORY_FAILURE_DISCOVERY_VERSION

    def __post_init__(self) -> None:
        for name in (
            "cluster_id", "family_id", "capability_id", "failed_requirement_id",
            "verifier_id",
        ):
            _identifier(getattr(self, name), name)
        if not self.trace_ids or self.trace_ids != tuple(sorted(set(self.trace_ids))):
            raise ValueError("failure cluster trace identities must be sorted and unique")
        if len(self.evidence_sha256s) != len(self.trace_ids):
            raise ValueError("failure cluster evidence is incomplete")
        if any(not _is_sha256(value) for value in self.evidence_sha256s):
            raise ValueError("failure cluster evidence digest is invalid")
        _aware(self.first_observed_at, "first_observed_at")
        _aware(self.last_observed_at, "last_observed_at")
        if self.first_observed_at > self.last_observed_at:
            raise ValueError("failure cluster observation bounds are reversed")
        _sha256(self.cluster_sha256, "cluster_sha256")
        if self.family_id != failure_family_id(
            self.capability_id, self.failed_requirement_id, self.verifier_id,
        ):
            raise ValueError("failure cluster family identity does not match")
        if self.cluster_sha256 != failure_cluster_digest(self):
            raise ValueError("failure cluster digest does not match")
        if self.cluster_id != f"failure-cluster-{self.cluster_sha256}":
            raise ValueError("failure cluster identity does not match its digest")
        if self.contract_version != FACTORY_FAILURE_DISCOVERY_VERSION:
            raise ValueError("unsupported factory failure discovery version")


@dataclass(frozen=True, slots=True)
class FactoryCapabilityProposal:
    proposal_id: str
    cluster_id: str
    family_id: str
    capability_id: str
    failed_requirement_id: str
    observation_count: int
    proposed_at: datetime
    training_authorized: bool = False
    contract_version: str = FACTORY_FAILURE_DISCOVERY_VERSION

    def __post_init__(self) -> None:
        for name in (
            "proposal_id", "cluster_id", "family_id", "capability_id",
            "failed_requirement_id",
        ):
            _identifier(getattr(self, name), name)
        if self.observation_count < 2:
            raise ValueError("factory proposals require repeated verified failures")
        _aware(self.proposed_at, "proposed_at")
        if self.training_authorized:
            raise ValueError("failure discovery cannot authorize training")
        if self.proposal_id != f"factory-proposal-{self.cluster_id.removeprefix('failure-cluster-')}":
            raise ValueError("factory proposal identity does not match its cluster")
        if self.contract_version != FACTORY_FAILURE_DISCOVERY_VERSION:
            raise ValueError("unsupported factory failure discovery version")


def build_verified_failure_trace(
    *, verification_id: str, request_id: str, candidate_id: str,
    capability_id: str, failed_requirement_id: str, verifier_id: str,
    verifier_artifact_sha256: str, candidate_sha256: str, model_ref: str,
    expert_tier: str, release_id: str, signer_key_id: str,
    observed_at: datetime,
) -> VerifiedFailureTrace:
    identity = _digest({
        "candidate_id": candidate_id,
        "verification_id": verification_id,
        "verifier_artifact_sha256": verifier_artifact_sha256,
    })
    values = {
        "trace_id": f"failure-trace-{identity}",
        "verification_id": verification_id,
        "request_id": request_id,
        "candidate_id": candidate_id,
        "capability_id": capability_id,
        "failed_requirement_id": failed_requirement_id,
        "verifier_id": verifier_id,
        "verifier_artifact_sha256": verifier_artifact_sha256,
        "candidate_sha256": candidate_sha256,
        "model_ref": model_ref,
        "expert_tier": expert_tier,
        "release_id": release_id,
        "signer_key_id": signer_key_id,
        "observed_at": observed_at,
        "independently_verified": True,
        "training_authorized": False,
        "contract_version": FACTORY_FAILURE_DISCOVERY_VERSION,
    }
    evidence_sha256 = _failure_trace_values_digest(values)
    return VerifiedFailureTrace(
        f"failure-trace-{identity}", verification_id, request_id, candidate_id,
        capability_id, failed_requirement_id, verifier_id,
        verifier_artifact_sha256, candidate_sha256, model_ref, expert_tier,
        release_id, signer_key_id, observed_at, evidence_sha256,
    )


def discover_failure_clusters(
    traces: tuple[VerifiedFailureTrace, ...], minimum_observations: int = 2,
) -> tuple[tuple[VerifiedFailureCluster, ...], tuple[FactoryCapabilityProposal, ...]]:
    if minimum_observations < 2:
        raise ValueError("factory discovery minimum must preserve repeated-failure evidence")
    identities = tuple(item.trace_id for item in traces)
    if len(set(identities)) != len(identities):
        raise ValueError("factory discovery traces must be unique")
    grouped: dict[str, list[VerifiedFailureTrace]] = {}
    for trace in traces:
        grouped.setdefault(trace.family_id, []).append(trace)
    clusters: list[VerifiedFailureCluster] = []
    proposals: list[FactoryCapabilityProposal] = []
    for family_id, values in sorted(grouped.items()):
        ordered = tuple(sorted(values, key=lambda item: item.trace_id))
        first = min(item.observed_at for item in ordered)
        last = max(item.observed_at for item in ordered)
        prototype = ordered[0]
        digest = _digest({
            "evidence_sha256s": [item.evidence_sha256 for item in ordered],
            "family_id": family_id,
            "trace_ids": [item.trace_id for item in ordered],
        })
        cluster = VerifiedFailureCluster(
            f"failure-cluster-{digest}", family_id, prototype.capability_id,
            prototype.failed_requirement_id, prototype.verifier_id,
            tuple(item.trace_id for item in ordered),
            tuple(item.evidence_sha256 for item in ordered), first, last, digest,
        )
        clusters.append(cluster)
        if len(ordered) >= minimum_observations:
            proposals.append(FactoryCapabilityProposal(
                f"factory-proposal-{digest}", cluster.cluster_id, family_id,
                cluster.capability_id, cluster.failed_requirement_id, len(ordered), last,
            ))
    return tuple(clusters), tuple(proposals)


def failure_family_id(capability_id: str, requirement_id: str, verifier_id: str) -> str:
    for name, value in (
        ("capability_id", capability_id), ("requirement_id", requirement_id),
        ("verifier_id", verifier_id),
    ):
        _identifier(value, name)
    return f"failure-family-{_digest([capability_id, requirement_id, verifier_id])}"


def failure_trace_digest(trace: VerifiedFailureTrace) -> str:
    return _failure_trace_values_digest({
        name: getattr(trace, name) for name in VerifiedFailureTrace.__dataclass_fields__
    })


def _failure_trace_values_digest(values: dict[str, object]) -> str:
    observed_at = values["observed_at"]
    if not isinstance(observed_at, datetime):
        raise TypeError("failure trace observation time is invalid")
    return _digest({
        name: observed_at.isoformat() if name == "observed_at" else values[name]
        for name in (
            "candidate_id", "candidate_sha256", "capability_id", "expert_tier",
            "failed_requirement_id", "model_ref", "observed_at", "release_id",
            "request_id", "signer_key_id", "trace_id", "verification_id",
            "verifier_artifact_sha256", "verifier_id",
        )
    })


def failure_cluster_digest(cluster: VerifiedFailureCluster) -> str:
    return _digest({
        "evidence_sha256s": list(cluster.evidence_sha256s),
        "family_id": cluster.family_id,
        "trace_ids": list(cluster.trace_ids),
    })


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is invalid")


def _is_sha256(value: str) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256(value: str, name: str) -> None:
    if not _is_sha256(value):
        raise ValueError(f"{name} must be lowercase SHA-256")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
