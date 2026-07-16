"""Pure deterministic host-memory admission policy."""

from dataclasses import dataclass

from fam_os.scheduler.admission_contracts import (
    AdmissionDecision,
    AdmissionRequest,
    AdmissionStatus,
)
from fam_os.scheduler.live_contracts import ObservationStatus
from fam_os.scheduler.residency_contracts import ExpertResidencyState


@dataclass(frozen=True, slots=True)
class DeterministicAdmissionPolicy:
    """Admit against RAM only; accelerator placement belongs to Phase 7.6."""

    def decide(self, decision_id: str, request: AdmissionRequest) -> AdmissionDecision:
        weight = (
            request.weight.resident_weight_bytes
            if request.requested_state is ExpertResidencyState.COLD else 0
        )
        context = request.context_memory_bytes
        required = weight + context
        if request.observation_status is ObservationStatus.DEGRADED:
            return _rejected(decision_id, request, weight, context, "resource_observation.degraded")
        if not request.memory_scope_authoritative:
            return _rejected(decision_id, request, weight, context, "memory_scope.not_authoritative")
        shortfall = max(0, required - request.available_memory_bytes)
        selected = []
        reclaimed = 0
        for candidate in _stable_candidates(request):
            if reclaimed >= shortfall:
                break
            selected.append(candidate.expert_id)
            reclaimed += candidate.reclaimable_bytes
        if reclaimed < shortfall:
            return _decision(
                decision_id, request, AdmissionStatus.REJECTED, weight, context,
                shortfall, tuple(selected), reclaimed, "memory.insufficient_after_safe_eviction",
            )
        reason = "memory.admitted_with_eviction" if selected else "memory.admitted_without_eviction"
        return _decision(
            decision_id, request, AdmissionStatus.ADMITTED, weight, context,
            shortfall, tuple(selected), reclaimed, reason,
        )


def _stable_candidates(request):
    eligible = (
        item for item in request.eviction_candidates
        if item.state is ExpertResidencyState.WARM and item.reclaimable_bytes > 0
    )
    return sorted(
        eligible,
        key=lambda item: (
            item.retention_priority,
            item.last_used_at,
            item.expert_id,
        ),
    )


def _rejected(decision_id, request, weight, context, reason):
    return _decision(
        decision_id, request, AdmissionStatus.REJECTED, weight, context,
        max(0, weight + context - request.available_memory_bytes), (), 0, reason,
    )


def _decision(decision_id, request, status, weight, context, shortfall, evictions, reclaimed, reason):
    available_after = max(
        0, request.available_memory_bytes + reclaimed - (weight + context)
    )
    return AdmissionDecision(
        decision_id, request.request_id, status, weight, context, weight + context,
        request.available_memory_bytes, shortfall, evictions, reclaimed,
        available_after, (reason, "placement.host_memory_only"),
    )
