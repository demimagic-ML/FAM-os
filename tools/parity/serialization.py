"""Stable JSON payload conversion for provider-neutral parity evidence."""

from __future__ import annotations

from fam_os.core.ports.inference import LoadedModel
from fam_os.routing.contracts import RoutingResult
from fam_os.supervisor.contracts import ResourceSnapshot
from fam_os.telemetry.contracts import InferenceMetrics
from fam_os.verification.contracts import VerificationReport


def metrics_payload(metrics: InferenceMetrics | None) -> dict[str, object] | None:
    if metrics is None:
        return None
    return {
        "model_ref": metrics.model_ref,
        "wall_seconds": metrics.wall_seconds,
        "load_seconds": metrics.load_seconds,
        "prompt_tokens": metrics.prompt_tokens,
        "output_tokens": metrics.output_tokens,
        "generation_tokens_per_second": metrics.generation_tokens_per_second,
    }


def loaded_models_payload(models: tuple[LoadedModel, ...]) -> list[dict[str, object]]:
    return [
        {
            "model_ref": model.model_ref,
            "resident_bytes": model.resident_bytes,
            "accelerator_bytes": model.accelerator_bytes,
            "context_tokens": model.context_tokens,
        }
        for model in models
    ]


def routing_payload(result: RoutingResult) -> dict[str, object]:
    decision = result.decision
    return {
        "route": decision.route.value,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "required_capabilities": list(decision.required_capabilities),
        "metrics": metrics_payload(result.metrics),
    }


def resource_payload(snapshot: ResourceSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "service_id": snapshot.service_id,
        "memory_current_bytes": snapshot.memory_current_bytes,
        "memory_peak_bytes": snapshot.memory_peak_bytes,
        "memory_limit_bytes": _ceiling(snapshot.memory_limit),
        "swap_current_bytes": snapshot.swap_current_bytes,
        "swap_limit_bytes": _ceiling(snapshot.swap_limit),
        "cpu_usage_microseconds": snapshot.cpu_usage_microseconds,
        "cpu_user_microseconds": snapshot.cpu_user_microseconds,
        "cpu_system_microseconds": snapshot.cpu_system_microseconds,
        "io_read_bytes": snapshot.io_read_bytes,
        "io_write_bytes": snapshot.io_write_bytes,
        "io_read_operations": snapshot.io_read_operations,
        "io_write_operations": snapshot.io_write_operations,
        "cpu_quota_percent": getattr(snapshot.cpu_quota, "maximum_percent", None),
        "tasks_current": snapshot.tasks_current,
        "tasks_limit": getattr(snapshot.tasks_limit, "maximum", None),
        "events": {event.name: event.count for event in snapshot.events},
        "pressure": [
            {
                "scope": sample.scope.value,
                "average_10": sample.average_10,
                "average_60": sample.average_60,
                "average_300": sample.average_300,
                "total_stall_microseconds": sample.total_stall_microseconds,
            }
            for sample in snapshot.pressure
        ],
    }


def verification_payload(report: VerificationReport) -> dict[str, object]:
    evidence = report.evidence
    return {
        "verification_id": report.verification_id,
        "verifier_id": report.verifier_id,
        "status": report.status.value,
        "stage": report.stage,
        "reason": report.reason,
        "wall_seconds": report.wall_seconds,
        "evidence": None
        if evidence is None
        else {
            "stdout": evidence.stdout,
            "stderr": evidence.stderr,
            "exit_code": evidence.exit_code,
            "normalized_candidate": evidence.normalized_candidate,
            "isolation": evidence.isolation,
        },
    }


def _ceiling(value: object) -> int | None:
    return getattr(value, "maximum_bytes", None)
