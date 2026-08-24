"""Supervised production observer for content-free verified failure discovery."""

from __future__ import annotations

import hashlib
from threading import RLock

from fam_os.expert_factory import (
    build_verified_failure_trace,
    discover_failure_clusters,
)
from fam_os.verification import VerificationStatus


class ProductFactoryDiscovery:
    def __init__(self, repositories, minimum_observations: int = 2) -> None:
        if minimum_observations < 2:
            raise ValueError("factory discovery requires repeated failures")
        self._repositories = repositories
        self._minimum = minimum_observations
        self._lock = RLock()
        self._active = False

    def start(self) -> None:
        with self._lock:
            self._active = True

    def stop(self) -> None:
        with self._lock:
            self._active = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def verification_failed(self, record, decision) -> None:
        with self._lock:
            if not self._active:
                return
            run = decision.run_record
            if run is None or run.status is not VerificationStatus.FAILED:
                return
            if run.effective_trust != "signed":
                return
            if run.release_id is None or run.signer_key_id is None:
                raise ValueError("signed failure evidence lacks release identity")
            if (
                run.request_id != record.request_id
                or run.candidate_id != record.candidate_id
                or run.verifier_id != decision.verifier_id
                or run.acceptance_id != decision.acceptance_id
            ):
                raise ValueError("factory failure evidence does not bind active verification")
            candidate = self._repositories.final_evidence.candidate(record.candidate_id)
            if candidate is None or candidate.request_id != record.request_id:
                raise RuntimeError("factory failure candidate evidence is unavailable")
            trace = build_verified_failure_trace(
                verification_id=run.verification_id,
                request_id=run.request_id,
                candidate_id=run.candidate_id,
                capability_id=f"intent.{record.intent.value}",
                failed_requirement_id=run.acceptance_id,
                verifier_id=run.verifier_id,
                verifier_artifact_sha256=run.verified_artifact_sha256,
                candidate_sha256=hashlib.sha256(
                    candidate.content.encode("utf-8"),
                ).hexdigest(),
                model_ref=record.selection.model_ref,
                expert_tier=record.selection.tier,
                release_id=run.release_id,
                signer_key_id=run.signer_key_id,
                observed_at=run.created_at,
            )
            if not self._repositories.factory_discovery.add_trace(trace):
                return
            clusters, proposals = discover_failure_clusters(
                self._repositories.factory_discovery.traces(trace.family_id),
                self._minimum,
            )
            for cluster in clusters:
                self._repositories.factory_discovery.add_cluster(cluster)
            for proposal in proposals:
                self._repositories.factory_discovery.add_proposal(proposal)

    def traces(self):
        return self._repositories.factory_discovery.traces()

    def clusters(self):
        return self._repositories.factory_discovery.clusters()

    def proposals(self):
        return self._repositories.factory_discovery.latest_proposals()
