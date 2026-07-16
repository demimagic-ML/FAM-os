"""Fail-closed resource admission for bounded predictive prefetch."""

from __future__ import annotations

from fam_os.scheduler.cache_contracts import CacheEntryState
from fam_os.scheduler.prefetch_contracts import (
    PrefetchAdmissionStatus,
    PrefetchPolicyDecision,
    PrefetchPolicyRequest,
)


class DeterministicPrefetchAdmissionPolicy:
    def decide(self, decision_id: str, request: PrefetchPolicyRequest):
        reasons: list[str] = []
        candidate = request.prediction.candidate
        budget = request.budget
        entry = next((item for item in request.snapshot.entries if (
            item.artifact_id == candidate.artifact_id and item.tier is candidate.tier
        )), None)
        if request.evaluated_at >= request.prediction.expires_at:
            reasons.append("prediction.expired")
        if entry is None:
            reasons.append("cache.candidate_unobserved")
        elif entry.state is not CacheEntryState.COLD:
            reasons.append("cache.candidate_already_resident")
        if candidate.requested_prefetch_bytes > budget.maximum_prefetch_bytes:
            reasons.append("budget.prefetch_bytes_exceeded")
        if candidate.requested_prefetch_bytes > budget.maximum_io_read_bytes:
            reasons.append("budget.io_read_bytes_exceeded")
        if candidate.requested_prefetch_bytes > budget.available_tier_bytes:
            reasons.append("capacity.tier_insufficient")
        remaining = budget.host_available_bytes - candidate.requested_prefetch_bytes
        if remaining < budget.operating_system_reserve_bytes:
            reasons.append("capacity.operating_system_reserve")
        if request.in_flight_prefetches >= budget.maximum_concurrent_prefetches:
            reasons.append("budget.concurrent_prefetches_exceeded")
        projected_waste = budget.current_waste_bytes + candidate.requested_prefetch_bytes
        if projected_waste > budget.maximum_waste_bytes:
            reasons.append("budget.maximum_waste_exceeded")
        if reasons:
            return PrefetchPolicyDecision(
                decision_id, request.request_id, PrefetchAdmissionStatus.REJECTED,
                0, 0, tuple(reasons), (),
            )
        return PrefetchPolicyDecision(
            decision_id, request.request_id, PrefetchAdmissionStatus.ADMITTED,
            candidate.requested_prefetch_bytes, candidate.requested_prefetch_bytes,
            ("prediction.supported", "capacity.within_all_bounds", "eviction.none"), (),
        )
