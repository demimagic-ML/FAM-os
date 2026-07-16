"""Translate captured scheduler documents into a replayable admission request."""

from fam_os.scheduler.admission_contracts import (
    AdmissionRequest,
    EvictionCandidate,
    ResidentWeightEstimate,
)
from fam_os.scheduler.context_contracts import ContextMemoryEstimate
from fam_os.scheduler.live_contracts import SchedulerResourceObservation
from fam_os.scheduler.residency_contracts import ExpertResidencyCatalog


def build_admission_request(
    request_id: str,
    expert_id: str,
    observation: SchedulerResourceObservation,
    catalog: ExpertResidencyCatalog,
    weight: ResidentWeightEstimate,
    context: ContextMemoryEstimate,
    retention_priorities: dict[str, int],
) -> AdmissionRequest:
    requested = catalog.require(expert_id)
    candidates = tuple(
        EvictionCandidate(
            record.identity.expert_id,
            record.state,
            record.resident_bytes or 0,
            retention_priorities.get(record.identity.expert_id, 100),
            record.transitioned_at,
        )
        for record in catalog.records
        if record.identity.expert_id != expert_id
    )
    return AdmissionRequest(
        request_id=request_id,
        observation_id=observation.observation_id,
        observation_status=observation.status,
        memory_scope_authoritative=observation.memory.scope_authoritative,
        available_memory_bytes=observation.memory.available_for_new_bytes,
        residency_catalog_id=catalog.catalog_id,
        residency_catalog_revision=catalog.revision,
        requested_expert_id=expert_id,
        requested_state=requested.state,
        weight=weight,
        context_estimate_id=context.estimate_id,
        context_memory_bytes=context.total_context_bytes,
        context_weights_excluded=context.model_resident_bytes_excluded,
        eviction_candidates=candidates,
    )
