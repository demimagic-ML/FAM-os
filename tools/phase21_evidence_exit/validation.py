"""Strict predicates for the signed installed Phase 21.5 exit evidence."""

from __future__ import annotations


_DIGEST_FIELDS = (
    "remote_plan_sha256",
    "execution_request_sha256",
    "execution_result_sha256",
    "context_content_sha256",
    "context_receipt_sha256",
    "candidate_sha256",
    "result_content_sha256",
)
_BOUND_REFERENCE_FIELDS = (
    "evidence_id",
    "instance_id",
    "request_id",
    "remote_plan_id",
    "execution_id",
    "enrollment_id",
    "peer_device_id",
    "expert_id",
    "model_ref",
    "capability_declaration_id",
    "context_evidence_id",
    "context_id",
    "budget_reservation_id",
    "budget_attempt_id",
    "candidate_id",
    "acceptance_id",
    "acceptance_evidence_id",
    "verification_run_id",
)


def phase21_5_passed(document: dict) -> bool:
    success = document["complete_scenario"]
    partial = document["partial_scenario"]
    remote_api = success["remote_execution"]
    evidence = remote_api.get("evidence") or {}
    success_route = success["installed_core_routes"]["remote"]
    partial_route = partial["installed_core_routes"]["partial"]
    partial_result = partial["terminal"]["result"]
    partial_server = partial["authenticated_partial_server"]
    partial_reservations = partial["database"]["reservations"][
        "task-phase21-partial-remote-frame"
    ]
    return all((
        document["desktop_install_healthy"],
        document["server_install_healthy"],
        document["release_component_count"] == 7,
        document["pairing_codes_match"],
        success["remote_terminal"]["result"]["status"] == "verified",
        success["remote_terminal"]["result"]["content"] == "READY",
        remote_api.get("available") is True,
        _complete_evidence(evidence),
        evidence == success_route["remote_execution_evidence"],
        evidence["evidence_id"]
        in success["remote_terminal"]["result"]["evidence_ids"],
        success["local_remote_execution"] == {
            "available": False,
            "evidence": None,
        },
        partial["request_count_delta"] == 1,
        partial["attempt_budget_count_delta"] == 1,
        len(partial_reservations) == 1,
        partial_reservations[0]["kind"] == "remote",
        partial_result["status"] == "failed",
        partial_result["verified"] is False,
        partial_result["content"] is None,
        partial["remote_execution"] == {"available": False, "evidence": None},
        partial_route["remote_plan_present"] is True,
        # Phase 21.6 owns disconnect reconciliation. Phase 21.5 proves the
        # durable reservation exists while the execution flag is still pending.
        partial_route["remote_attempt_consumed"] is False,
        partial_route["candidate_present"] is False,
        partial_route["remote_execution_evidence"] is None,
        partial_route["failure_code"] == "expert.generation.failed",
        partial["database"]["final_evidence_counts"][
            "task-phase21-partial-remote-frame"
        ] == 0,
        partial["context_disclosure_count_before"]
        == partial["context_disclosure_count_after"],
        partial_server["complete_frame_sent"] is False,
        partial_server["sent_response_bytes"]
        < partial_server["declared_response_bytes"],
        not partial["database_contains_partial_sentinel"],
        not success["evidence_contains_prompt"],
        not success["database_contains_prompt"],
    ))


def _complete_evidence(evidence: dict) -> bool:
    return all((
        all(isinstance(evidence.get(name), str) and evidence[name] for name in _BOUND_REFERENCE_FIELDS),
        all(_digest(evidence.get(name)) for name in _DIGEST_FIELDS),
        evidence.get("contract_version")
        == "fam.fabric.remote-execution-evidence/v1alpha1",
        evidence.get("disposition") == "released",
        evidence.get("verification_outcome") == "passed",
        evidence.get("expert_tier") == "escalation",
        evidence.get("model_ref") == "gemma4:26b",
        evidence.get("context_content_bytes", 0) > 0,
        evidence.get("result_content_bytes", 0) > 0,
        evidence.get("candidate_sha256") == evidence.get("result_content_sha256"),
        evidence.get("raw_content_retained") is False,
        evidence.get("partial_output_retained") is False,
        isinstance(evidence.get("authenticated_at"), str),
        isinstance(evidence.get("finalized_at"), str),
    ))


def _digest(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
