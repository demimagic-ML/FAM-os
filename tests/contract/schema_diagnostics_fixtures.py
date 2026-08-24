"""Representative runtime-diagnostics schema values."""

from datetime import datetime, timedelta, timezone

from fam_os.core.engineering import (
    DiagnosticArtifactKind,
    RuntimeDiagnosticArtifact,
    RuntimeDiagnosticKind,
    RuntimeDiagnosticLimits,
    RuntimeDiagnosticPhase,
    RuntimePerformanceMode,
    RuntimeDiagnosticReceipt,
    RuntimeDiagnosticRequest,
    RuntimeDiagnosticStatus,
    SandboxNetworkMode,
)


NOW = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def diagnostics_schema_values() -> tuple[object, ...]:
    limits = RuntimeDiagnosticLimits(
        60, 30, 268_435_456, 16, 1_000_000, 4_000_000, 10_000,
        64_000_000,
    )
    request = RuntimeDiagnosticRequest(
        "diagnostic-request-1", "task-1", "candidate-1", "grant-1",
        "owner-1", "session-1", RuntimeDiagnosticPhase.CANDIDATE,
        "recipe-perf-1", "1.0.0",
        DIGEST_A, RuntimeDiagnosticKind.PERFORMANCE_REGRESSION,
        ("python", "benchmark.py"), ("PYTHONPATH",),
        (DiagnosticArtifactKind.PERFORMANCE_SAMPLE,), limits,
        SandboxNetworkMode.DENIED, (), NOW, DIGEST_B, 1_000_000, 50_000,
        performance_mode=RuntimePerformanceMode.COMPARISON,
    )
    artifact = RuntimeDiagnosticArtifact(
        "diagnostic-artifact-1", DiagnosticArtifactKind.PERFORMANCE_SAMPLE,
        "application/json", DIGEST_A, 512, True,
    )
    receipt = RuntimeDiagnosticReceipt(
        "diagnostic-receipt-1", request.request_id, request.task_id,
        request.candidate_id, request.signed_recipe_id,
        request.signed_recipe_version,
        request.recipe_payload_sha256, "sandbox-engineering-1", NOW,
        NOW + timedelta(seconds=2), RuntimeDiagnosticStatus.PASSED, 0,
        DIGEST_A, DIGEST_B, (artifact,), ("finding-1",),
        ("isolation-1",), ("authorization-1",),
        request.baseline_artifact_sha256, 1_010_000,
        10_000,
        performance_mode=RuntimePerformanceMode.COMPARISON,
    )
    return request, receipt
