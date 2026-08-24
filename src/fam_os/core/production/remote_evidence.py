"""Build content-free evidence from one fully authenticated remote candidate."""

from __future__ import annotations

import hashlib

from fam_os.core.lifecycle import AttemptBudgetReservation, CandidateEvidenceRecord
from fam_os.core.production.contracts import InferenceExecutionRecord
from fam_os.core.production.generation_input import AuthenticatedRemoteInference
from fam_os.fabric import (
    RemoteEvidenceDisposition,
    RemoteExecutionEvidence,
    RemoteVerificationOutcome,
)
from fam_os.schemas import dumps_document


def authenticated_remote_evidence(
    record: InferenceExecutionRecord,
    exchange: AuthenticatedRemoteInference,
    reservation: AttemptBudgetReservation,
    candidate: CandidateEvidenceRecord,
) -> RemoteExecutionEvidence:
    plan = record.remote_plan
    if plan is None or not record.remote_attempt_consumed:
        raise ValueError("remote evidence requires one durably reserved Core route")
    request = exchange.execution_request
    result = exchange.execution_result
    disclosure = exchange.context_evidence
    if (
        plan.plan_id != request.plan_id
        or plan.instance_id != record.instance_id
        or plan.request_id != record.request_id
        or result.request_id != disclosure.request_id
        or disclosure.context_id != request.context.context_id
        or candidate.request_id != record.request_id
        or reservation.plan_instance_id != record.instance_id
    ):
        raise ValueError("remote evidence identities do not match Core")
    candidate_sha256 = _sha256(candidate.content.encode("utf-8"))
    if candidate_sha256 != result.content_sha256:
        raise ValueError("remote candidate digest differs from signed result")
    return RemoteExecutionEvidence(
        evidence_id=_evidence_id(request.execution_id),
        instance_id=record.instance_id,
        request_id=record.request_id,
        remote_plan_id=plan.plan_id,
        remote_plan_sha256=_contract_sha256(plan),
        execution_id=request.execution_id,
        execution_request_sha256=_contract_sha256(request),
        execution_result_sha256=_contract_sha256(result),
        enrollment_id=plan.enrollment_id,
        peer_device_id=plan.peer_device_id,
        expert_id=plan.expert_id,
        model_ref=plan.model_ref,
        expert_tier=plan.expert_tier,
        capability_declaration_id=plan.capability_declaration_id,
        context_evidence_id=disclosure.evidence_id,
        context_id=disclosure.context_id,
        context_content_bytes=disclosure.content_bytes,
        context_content_sha256=disclosure.content_sha256,
        context_receipt_sha256=_contract_sha256(result.context_receipt),
        budget_reservation_id=reservation.reservation_id,
        budget_attempt_id=reservation.attempt_id,
        candidate_id=candidate.candidate_id,
        candidate_sha256=candidate_sha256,
        result_content_bytes=result.content_bytes,
        result_content_sha256=result.content_sha256,
        disposition=RemoteEvidenceDisposition.AUTHENTICATED_CANDIDATE,
        verification_outcome=RemoteVerificationOutcome.PENDING,
        acceptance_id=None,
        acceptance_evidence_id=None,
        verification_run_id=None,
        authenticated_at=result.completed_at,
        finalized_at=None,
    )


def _evidence_id(execution_id: str) -> str:
    return "remote-evidence-" + _sha256(execution_id.encode("utf-8"))[:32]


def _contract_sha256(value: object) -> str:
    return _sha256(dumps_document(value).encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
