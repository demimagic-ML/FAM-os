"""Explicit gates for Phase 1 measured parity artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True, slots=True)
class ParityCheck:
    name: str
    passed: bool
    detail: str


def routing_checks(report: Mapping[str, Any]) -> tuple[ParityCheck, ...]:
    summary = report["models"][0]["summary"]
    route_totals = tuple(item["total"] for item in summary["by_expected_route"].values())
    return (
        _check("routing_case_count", summary["total"] == 24, str(summary["total"])),
        _check("routing_balance", route_totals == (6, 6, 6, 6), str(route_totals)),
        _check("routing_accuracy", summary["accuracy"] >= 23 / 24, str(summary["accuracy"])),
        _check(
            "routing_structured_rate",
            summary["valid_json_rate"] >= 23 / 24,
            str(summary["valid_json_rate"]),
        ),
        *_resource_checks(report),
    )


def activation_checks(report: Mapping[str, Any]) -> tuple[ParityCheck, ...]:
    loaded = report["loaded_after_expert"]
    cpu_only = all((item["accelerator_bytes"] or 0) == 0 for item in loaded)
    gpu_expected = bool(report["constraints"]["gpu_allowed"])
    placement_matches = (not cpu_only) if gpu_expected else cpu_only
    return (
        _check("activation_route", report["routing"]["route"] == "code", report["routing"]["route"]),
        _check("activation_status", report["status"] == "activated", report["status"]),
        _check("activation_device_placement", placement_matches, str(cpu_only)),
        *_resource_checks(report),
    )


def policy_comparison_checks(
    reports: Mapping[str, Mapping[str, Any]],
) -> tuple[ParityCheck, ...]:
    persistent_14 = reports["persistent-kernel-14b-expert"]
    evict_14 = reports["evict-kernel-14b-expert"]
    persistent_7 = reports["persistent-kernel-7b-expert"]
    p14_peak = persistent_14["resources"]["memory_peak_bytes"]
    e14_peak = evict_14["resources"]["memory_peak_bytes"]
    p7_peak = persistent_7["resources"]["memory_peak_bytes"]
    p14_rate = persistent_14["expert_metrics"]["generation_tokens_per_second"]
    p7_rate = persistent_7["expert_metrics"]["generation_tokens_per_second"]
    return (
        _check("eviction_reduces_14b_peak", e14_peak < p14_peak, f"{e14_peak} < {p14_peak}"),
        _check("7b_reduces_peak", p7_peak < p14_peak, f"{p7_peak} < {p14_peak}"),
        _check("7b_improves_throughput", p7_rate > p14_rate, f"{p7_rate} > {p14_rate}"),
    )


def verified_checks(report: Mapping[str, Any]) -> tuple[ParityCheck, ...]:
    attempts = report["attempts"]
    kinds = tuple(attempt["kind"] for attempt in attempts)
    passing = tuple(
        attempt for attempt in attempts if attempt["verification"]["status"] == "passed"
    )
    result = report["result"]
    final_matches = bool(passing) and result["content"] == passing[-1]["candidate"]
    return (
        _check("verified_route", report["routing"]["route"] == "code", report["routing"]["route"]),
        _check("verified_release", result["verified"] is True, str(result["verified"])),
        _check(
            "verified_escalation",
            "escalation" in kinds and report["status"] == "verified_after_escalation",
            f"{report['status']} {kinds}",
        ),
        _check("passing_candidate_only", final_matches, str(final_matches)),
        *_resource_checks(report),
    )


def checks_payload(checks: tuple[ParityCheck, ...]) -> list[dict[str, object]]:
    return [
        {"name": check.name, "passed": check.passed, "detail": check.detail}
        for check in checks
    ]


def _resource_checks(report: Mapping[str, Any]) -> tuple[ParityCheck, ...]:
    resources = report["resources"]
    events = resources["events"]
    constraints = report["constraints"]
    expected_memory = constraints["service_memory_max_bytes"]
    observed_memory = resources["memory_limit_bytes"]
    if expected_memory is None:
        memory_matches = observed_memory is None or observed_memory >= constraints["memory_scheduler_limit_bytes"]
    else:
        memory_matches = observed_memory == expected_memory
    return (
        _check(
            "memory_ceiling",
            memory_matches,
            str(observed_memory),
        ),
        _check(
            "swap_ceiling",
            resources["swap_limit_bytes"] == constraints["service_swap_max_bytes"],
            str(resources["swap_limit_bytes"]),
        ),
        _check("no_oom_kill", events.get("oom_kill", 0) == 0, str(events.get("oom_kill", 0))),
    )


def _check(name: str, passed: bool, detail: str) -> ParityCheck:
    return ParityCheck(name, passed, detail)
