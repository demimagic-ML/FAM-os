"""Strict predicates for signed installed Phase 21.6 recovery evidence."""

from __future__ import annotations


def phase21_6_passed(document: dict) -> bool:
    scenario = document["scenario"]
    interrupted = scenario["interrupted_state"]
    final = scenario["installed_state"]
    result = scenario["terminal"]["result"]
    recovery_api = scenario["remote_recovery"]
    recovery = recovery_api.get("evidence") or {}
    loss = scenario["loss_server"]
    verification = scenario["verifications"]
    reservations = scenario["database"]["reservations"][
        "task-phase21-remote-loss-restart"
    ]
    remote_reservation = final["remote_reservation"] or {}
    local_reservation = final["local_recovery_reservation"] or {}
    budget = final["budget"] or {}
    return all((
        document["desktop_install_healthy"],
        document["server_install_healthy"],
        document["release_component_count"] == 7,
        document["pairing_codes_match"],
        scenario["declared_remote_model"] == "gemma4:26b",
        scenario["privacy_revision"] == 1,
        loss["authenticated_peer"]["tls_version"] == "TLSv1.3",
        loss["requester_loss_observed"] is True,
        loss["request_content_bytes"] > 0,
        loss["response_bytes_sent"] == 0,
        interrupted["state"] == "running",
        interrupted["remote_plan_present"] is True,
        interrupted["remote_attempt_consumed"] is True,
        interrupted["remote_execution_evidence"] is None,
        interrupted["remote_recovery_evidence"] is None,
        interrupted["remote_reservation"] is not None,
        interrupted["local_recovery_reservation"] is None,
        result["status"] == "verified",
        result["verified"] is True,
        result["content"] == "READY",
        scenario["remote_execution"] == {"available": False, "evidence": None},
        recovery_api.get("available") is True,
        _valid_recovery(recovery),
        recovery["evidence_id"] in result["evidence_ids"],
        final["state"] == "terminal",
        final["assurance"] == "verified",
        final["candidate_present"] is True,
        final["remote_attempt_consumed"] is True,
        final["selection_model_ref"] == recovery["local_model_ref"],
        final["remote_execution_evidence"] is None,
        final["remote_recovery_evidence"] == recovery,
        remote_reservation["kind"] == "remote",
        local_reservation["kind"] == "local_recovery",
        remote_reservation["acceptance_sha256"]
        == local_reservation["acceptance_sha256"]
        == recovery["accepted_contract_sha256"],
        remote_reservation["route_plan_id"] == recovery["remote_plan_id"],
        local_reservation["route_plan_id"] == recovery["remote_plan_id"],
        budget["consumed_tokens"] == 2048,
        budget["consumed_wall_milliseconds"] == 600_000,
        len(budget["reservation_ids"]) == 2,
        {item["kind"] for item in reservations} == {"remote", "local_recovery"},
        len(verification) == 1,
        verification[0]["status"] == "passed",
        verification[0]["effective_trust"] == "signed",
        scenario["desktop_context_count_before"]
        == scenario["desktop_context_count_after"] == 0,
        scenario["server_context_count_before"] == 0,
        not scenario["database_contains_prompt"],
    ))


def _valid_recovery(evidence: dict) -> bool:
    return all((
        evidence.get("contract_version")
        == "fam.fabric.remote-recovery-evidence/v1alpha1",
        evidence.get("failure") == "uncertain_completion",
        evidence.get("disposition") == "recovered",
        evidence.get("unchanged_acceptance") is True,
        evidence.get("local_retry_allowed") is True,
        evidence.get("accepted_contract_sha256")
        == evidence.get("observed_contract_sha256"),
        isinstance(evidence.get("local_candidate_id"), str),
        isinstance(evidence.get("local_model_ref"), str),
        evidence.get("raw_content_retained") is False,
        evidence.get("partial_output_retained") is False,
        isinstance(evidence.get("finalized_at"), str),
    ))
