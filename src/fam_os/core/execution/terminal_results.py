"""Safe terminal-result assembly for verified execution."""

from __future__ import annotations

from fam_os.core.contracts import (
    DegradationDisposition,
    DegradationImpact,
    DegradationKind,
    DegradationNotice,
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    ResultStatus,
    RetryDisposition,
    TaskResult,
)
from fam_os.core.execution.attempt import CandidateGenerationError
from fam_os.core.execution.errors import ExecutionConfigurationError
from fam_os.core.execution.placement import PlacementExecutionError


ExecutionFailure = CandidateGenerationError | ExecutionConfigurationError | PlacementExecutionError


def verification_failed_result(request_id: str, evidence_id: str) -> TaskResult:
    message = "Candidate did not satisfy required verification."
    failure = FailureEnvelope(
        error_id=f"{request_id}:verification-failed",
        category=FailureCategory.VERIFICATION_FAILED,
        code="verification.acceptance.failed",
        safe_message=message,
        component=FailureComponent.VERIFICATION,
        retry=RetryDisposition.NEVER,
        evidence_ids=(evidence_id,),
    )
    return TaskResult(
        request_id,
        ResultStatus.WITHHELD,
        None,
        reason=message,
        evidence_ids=(evidence_id,),
        failure=failure,
    )


def unsupported_route_result(request_id: str, route: str) -> TaskResult:
    message = "This verified code workflow cannot serve the selected route."
    degradation = DegradationNotice(
        degradation_id=f"{request_id}:unsupported-route",
        kind=DegradationKind.CAPABILITY_UNAVAILABLE,
        code="core.route.unsupported",
        safe_message=message,
        component=FailureComponent.CORE,
        impact=DegradationImpact.HIGH,
        disposition=DegradationDisposition.WITHHOLD,
        original_capability_id=f"route.{route}",
    )
    return TaskResult(
        request_id,
        ResultStatus.WITHHELD,
        None,
        reason=message,
        degradations=(degradation,),
    )


def execution_failed_result(request_id: str, error: ExecutionFailure) -> TaskResult:
    category, code, message, component, retry = _classify_execution_error(error)
    failure = FailureEnvelope(
        error_id=f"{request_id}:execution-failed",
        category=category,
        code=code,
        safe_message=message,
        component=component,
        retry=retry,
    )
    return TaskResult(
        request_id,
        ResultStatus.FAILED,
        None,
        reason=message,
        failure=failure,
    )


def _classify_execution_error(
    error: ExecutionFailure,
) -> tuple[FailureCategory, str, str, FailureComponent, RetryDisposition]:
    if isinstance(error, CandidateGenerationError):
        return (
            FailureCategory.PROVIDER_FAILURE,
            "expert.generation.failed",
            "The selected expert could not generate a candidate.",
            FailureComponent.EXPERT,
            RetryDisposition.WITH_BACKOFF,
        )
    if isinstance(error, PlacementExecutionError):
        return (
            FailureCategory.RESOURCE_EXHAUSTED,
            "scheduler.placement.failed",
            "The selected expert could not be placed within the resource budget.",
            FailureComponent.SCHEDULER,
            RetryDisposition.AFTER_RESOURCE_CHANGE,
        )
    return (
        FailureCategory.INCOMPATIBLE,
        "core.execution.configuration-invalid",
        "The execution policy references unavailable or incompatible components.",
        FailureComponent.CORE,
        RetryDisposition.AFTER_USER_ACTION,
    )
