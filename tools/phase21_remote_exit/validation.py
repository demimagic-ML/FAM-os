"""Strict exit predicates for installed Phase 21.4 evidence."""

from __future__ import annotations


def phase21_4_passed(document: dict) -> bool:
    scenario = document["scenario"]
    remote_result = scenario["remote_terminal"]["result"]
    local_result = scenario["local_terminal"]["result"]
    remote_reservations = scenario["database"]["reservations"][
        "task-phase21-remote-gemma"
    ]
    local_reservations = scenario["database"]["reservations"][
        "task-phase21-local-baseline"
    ]
    verification = scenario["remote_verifications"]
    context = scenario["server_context_counts"]
    remote_route = scenario["installed_core_routes"]["remote"]
    local_route = scenario["installed_core_routes"]["local"]
    return all((
        document["desktop_install_healthy"],
        document["server_install_healthy"],
        document["release_component_count"] == 7,
        document["pairing_codes_match"],
        scenario["declared_remote_model"] == "gemma4:26b",
        scenario["privacy_revision"] == 1,
        all(scenario["denials"].values()),
        scenario["request_count_unchanged_by_denials"],
        scenario["server_context_unchanged_by_denials"],
        "selected gemma4:26b" in scenario["remote_accepted"]["message"],
        remote_result["status"] == "verified",
        remote_result["verified"] is True,
        remote_result["content"] == "READY",
        len(verification) == 1,
        verification[0]["status"] == "passed",
        verification[0]["effective_trust"] == "signed",
        _one_kind(remote_reservations, "remote"),
        local_result["status"] == "verified",
        local_result["content"] == "READY",
        local_reservations == [],
        scenario["database"]["attempt_budget_count"] == 2,
        remote_route["remote_plan_present"] is True,
        remote_route["remote_attempt_consumed"] is True,
        remote_route["selection_model_ref"] == "gemma4:26b",
        remote_route["selection_tier"] == "escalation",
        remote_route["remote_plan_expert_tier"] == "escalation",
        local_route["remote_plan_present"] is False,
        local_route["remote_attempt_consumed"] is False,
        local_route["state"] == "terminal",
        local_route["assurance"] == "verified",
        context["after_remote"] == context["after_denials"] + 1,
        context["after_local"] == context["after_remote"],
        scenario["desktop_context_evidence_count"] == 1,
        scenario["server_context_evidence_count"] == 1,
        not scenario["evidence_contains_prompt"],
        not scenario["database_contains_prompt"],
    ))


def _one_kind(reservations: list[dict], kind: str) -> bool:
    return len(reservations) == 1 and reservations[0].get("kind") == kind
