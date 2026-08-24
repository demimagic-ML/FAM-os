"""Fail-closed validation for two-host Phase 21.7 evidence."""

from __future__ import annotations

import hashlib
import json

from fam_os.fabric import (
    PhysicalHostEvidence,
    PhysicalHostRole,
    verify_physical_host_evidence,
)
from fam_os.schemas import loads_document


def physical_hosts_valid(requester: dict, peer: dict) -> bool:
    try:
        requester_value = _physical_host(requester)
        peer_value = _physical_host(peer)
        verify_physical_host_evidence(requester_value)
        verify_physical_host_evidence(peer_value)
    except (KeyError, TypeError, ValueError):
        return False
    return all((
        requester_value.role is PhysicalHostRole.REQUESTER,
        peer_value.role is PhysicalHostRole.EXPERT_PEER,
        requester_value.physical_host is True,
        peer_value.physical_host is True,
        requester_value.virtualization_kind == "none",
        peer_value.virtualization_kind == "none",
        requester_value.installation_healthy is True,
        peer_value.installation_healthy is True,
        requester_value.qualification_id == peer_value.qualification_id,
        requester_value.release_id == peer_value.release_id,
        requester_value.signer_key_id == peer_value.signer_key_id,
        requester_value.release_manifest_sha256
        == peer_value.release_manifest_sha256,
        requester_value.release_component_count
        == peer_value.release_component_count == 7,
        requester_value.device_id != peer_value.device_id,
        requester_value.device_fingerprint_sha256
        != peer_value.device_fingerprint_sha256,
        requester_value.machine_id_sha256 != peer_value.machine_id_sha256,
        requester_value.hardware_anchor_sha256
        != peer_value.hardware_anchor_sha256,
        requester_value.hostname_sha256 != peer_value.hostname_sha256,
        requester_value.network_interface_count > 0,
        peer_value.network_interface_count > 0,
        bool(requester_value.non_loopback_address_sha256),
        bool(peer_value.non_loopback_address_sha256),
    ))


def phase21_7_passed(document: dict) -> bool:
    try:
        requester = _physical_host(document["requester_host"])
        peer = _physical_host(document["peer_host"])
        pairing = _mapping(document["pairing"])
        success = _mapping(document["remote_success"])
        loss = _mapping(document["peer_loss_recovery"])
        diagnoses = _mapping(document["diagnoses"])
        removal = _mapping(document["removal"])
        success_evidence = _mapping(success["remote_execution_evidence"])
        success_budget = _mapping(success["remote_budget_reservation"])
        success_verification = _mapping(success["verification_run"])
        success_result = _mapping(success["terminal_result"])
        recovery = _mapping(loss["remote_recovery_evidence"])
        remote_budget = _mapping(loss["remote_budget_reservation"])
        local_budget = _mapping(loss["local_budget_reservation"])
        loss_verification = _mapping(loss["verification_run"])
        loss_result = _mapping(loss["terminal_result"])
    except (KeyError, TypeError, ValueError):
        return False

    ready_sha256 = hashlib.sha256(b"READY").hexdigest()
    requester_id = requester.device_id
    peer_id = peer.device_id
    return all((
        document.get("phase") == "21.7",
        document.get("qualification_id") == requester.qualification_id,
        document.get("release_id") == requester.release_id,
        document.get("signer_key_id") == requester.signer_key_id,
        document.get("release_manifest_sha256")
        == requester.release_manifest_sha256,
        physical_hosts_valid(document["requester_host"], document["peer_host"]),
        pairing.get("requester_device_id") == requester_id,
        pairing.get("peer_device_id") == peer_id,
        pairing.get("pairing_codes_match") is True,
        pairing.get("requester_enrollment_active") is True,
        pairing.get("peer_enrollment_active") is True,
        isinstance(pairing.get("requester_enrollment_id"), str),
        isinstance(pairing.get("peer_enrollment_id"), str),
        _digest(pairing.get("ceremony_sha256")),
        _success_valid(
            success, success_evidence, success_budget, success_verification,
            success_result, requester_id, peer_id, ready_sha256,
        ),
        _loss_valid(
            loss, recovery, remote_budget, local_budget, loss_verification,
            loss_result, requester_id, peer_id, ready_sha256,
        ),
        diagnoses.get("requester_healthy") is True,
        diagnoses.get("peer_healthy") is True,
        removal.get("requester_install_absent") is True,
        removal.get("peer_install_absent") is True,
        removal.get("requester_state_absent") is True,
        removal.get("peer_state_absent") is True,
        document.get("raw_prompt_retained") is False,
        document.get("unauthorized_context_count") == 0,
    ))


def phase21_7_tooling_smoke_passed(document: dict) -> bool:
    """Validate installed tooling while explicitly rejecting it as physical proof."""
    try:
        requester = _physical_host(document["requester_host"])
        peer = _physical_host(document["peer_host"])
        verify_physical_host_evidence(requester)
        verify_physical_host_evidence(peer)
        success = _mapping(document["remote_success"])
        loss = _mapping(document["peer_loss_recovery"])
        success_evidence = _mapping(success["remote_execution_evidence"])
        success_budget = _mapping(success["remote_budget_reservation"])
        success_verification = _mapping(success["verification_run"])
        success_result = _mapping(success["terminal_result"])
        recovery = _mapping(loss["remote_recovery_evidence"])
        remote_budget = _mapping(loss["remote_budget_reservation"])
        local_budget = _mapping(loss["local_budget_reservation"])
        loss_verification = _mapping(loss["verification_run"])
        loss_result = _mapping(loss["terminal_result"])
    except (KeyError, TypeError, ValueError):
        return False
    ready_sha256 = hashlib.sha256(b"READY").hexdigest()
    return all((
        document.get("phase") == "21.7-tooling-smoke",
        document.get("same_physical_host") is True,
        document.get("physical_gate_satisfied") is False,
        not physical_hosts_valid(document["requester_host"], document["peer_host"]),
        requester.role is PhysicalHostRole.REQUESTER,
        peer.role is PhysicalHostRole.EXPERT_PEER,
        requester.physical_host is True,
        peer.physical_host is True,
        requester.machine_id_sha256 == peer.machine_id_sha256,
        requester.hardware_anchor_sha256 == peer.hardware_anchor_sha256,
        requester.device_id != peer.device_id,
        requester.qualification_id == peer.qualification_id,
        requester.release_manifest_sha256 == peer.release_manifest_sha256,
        _success_valid(
            success, success_evidence, success_budget, success_verification,
            success_result, requester.device_id, peer.device_id, ready_sha256,
        ),
        _loss_valid(
            loss, recovery, remote_budget, local_budget, loss_verification,
            loss_result, requester.device_id, peer.device_id, ready_sha256,
        ),
        document.get("requester_diagnosis_healthy") is True,
        document.get("peer_diagnosis_healthy") is True,
        document.get("complete_removal") is True,
        document.get("raw_prompt_retained") is False,
    ))


def _success_valid(
    success: dict, evidence: dict, budget: dict, verification: dict,
    result: dict, requester_id: str, peer_id: str, ready_sha256: str,
) -> bool:
    request_id = success.get("request_id")
    evidence_id = evidence.get("evidence_id")
    verification_id = verification.get("verification_id")
    return all((
        isinstance(request_id, str),
        success.get("requester_device_id") == requester_id,
        success.get("peer_device_id") == peer_id,
        success.get("mutual_tls_version") == "TLSv1.3",
        success.get("remote_model") == "gemma4:26b",
        success.get("verified") is True,
        success.get("content") == "READY",
        success.get("requester_context_evidence_delta") == 1,
        success.get("peer_context_evidence_delta") == 1,
        success.get("unauthorized_context_count") == 0,
        success.get("requester_prompt_retained") is False,
        success.get("peer_prompt_retained") is False,
        evidence.get("contract_version")
        == "fam.fabric.remote-execution-evidence/v1alpha1",
        evidence.get("request_id") == request_id,
        evidence.get("peer_device_id") == peer_id,
        evidence.get("model_ref") == "gemma4:26b",
        evidence.get("disposition") == "released",
        evidence.get("verification_outcome") == "passed",
        evidence.get("verification_run_id") == verification_id,
        evidence.get("budget_reservation_id") == budget.get("reservation_id"),
        evidence.get("result_content_sha256") == ready_sha256,
        evidence.get("raw_content_retained") is False,
        evidence.get("partial_output_retained") is False,
        budget.get("kind") == "remote",
        budget.get("route_plan_id") == evidence.get("remote_plan_id"),
        _digest(budget.get("acceptance_sha256")),
        verification.get("status") == "passed",
        verification.get("effective_trust") == "signed",
        result.get("request_id") == request_id,
        result.get("status") == "verified",
        result.get("verified") is True,
        result.get("content") == "READY",
        evidence_id in result.get("evidence_ids", ()),
        verification_id in result.get("evidence_ids", ()),
    ))


def _loss_valid(
    loss: dict, recovery: dict, remote_budget: dict, local_budget: dict,
    verification: dict, result: dict, requester_id: str, peer_id: str,
    ready_sha256: str,
) -> bool:
    request_id = loss.get("request_id")
    evidence_id = recovery.get("evidence_id")
    verification_id = verification.get("verification_id")
    acceptance = recovery.get("accepted_contract_sha256")
    route_plan_id = recovery.get("remote_plan_id")
    return all((
        isinstance(request_id, str),
        loss.get("requester_device_id") == requester_id,
        loss.get("peer_device_id") == peer_id,
        loss.get("peer_stopped_before_request") is True,
        loss.get("peer_port_closed") is True,
        loss.get("remote_attempt_consumed") is True,
        loss.get("remote_execution_evidence") is None,
        loss.get("verified") is True,
        loss.get("content") == "READY",
        loss.get("requester_context_evidence_delta") == 0,
        loss.get("peer_context_evidence_delta") == 0,
        loss.get("requester_prompt_retained") is False,
        loss.get("peer_prompt_retained") is False,
        loss.get("peer_authenticated_after_restart") is True,
        recovery.get("contract_version")
        == "fam.fabric.remote-recovery-evidence/v1alpha1",
        recovery.get("request_id") == request_id,
        recovery.get("failure") in {"disconnected", "timeout"},
        recovery.get("disposition") == "recovered",
        recovery.get("unchanged_acceptance") is True,
        recovery.get("local_retry_allowed") is True,
        recovery.get("observed_contract_sha256") == acceptance,
        recovery.get("remote_budget_reservation_id")
        == remote_budget.get("reservation_id"),
        recovery.get("local_budget_reservation_id")
        == local_budget.get("reservation_id"),
        recovery.get("partial_output_retained") is False,
        recovery.get("raw_content_retained") is False,
        remote_budget.get("kind") == "remote",
        local_budget.get("kind") == "local_recovery",
        remote_budget.get("acceptance_sha256")
        == local_budget.get("acceptance_sha256") == acceptance,
        remote_budget.get("route_plan_id")
        == local_budget.get("route_plan_id") == route_plan_id,
        verification.get("status") == "passed",
        verification.get("effective_trust") == "signed",
        result.get("request_id") == request_id,
        result.get("status") == "verified",
        result.get("verified") is True,
        result.get("content") == "READY",
        hashlib.sha256(result.get("content", "").encode("utf-8")).hexdigest()
        == ready_sha256,
        evidence_id in result.get("evidence_ids", ()),
        verification_id in result.get("evidence_ids", ()),
    ))


def _physical_host(value: dict) -> PhysicalHostEvidence:
    loaded = loads_document(json.dumps(value, sort_keys=True))
    if not isinstance(loaded, PhysicalHostEvidence):
        raise TypeError("physical qualification host evidence is invalid")
    return loaded


def _mapping(value) -> dict:
    if not isinstance(value, dict):
        raise TypeError("physical qualification section is not an object")
    return value


def _digest(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
