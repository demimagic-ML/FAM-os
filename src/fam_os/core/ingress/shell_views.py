"""Server-side projection of trusted Core lifecycle state for FAM Shell."""

from fam_os.core.contracts import StepOutcome, TaskResult, TerminalDisposition
from fam_os.core.lifecycle.contracts import PlanInstanceSnapshot
from fam_os.shell import (
    ShellApprovalRequest,
    ShellPlanStep,
    ShellResult,
    ShellRunState,
    ShellSessionSnapshot,
    ShellStepState,
)


OUTCOME_STATES = {
    StepOutcome.SUCCEEDED: ShellStepState.SUCCEEDED,
    StepOutcome.FAILED: ShellStepState.FAILED,
    StepOutcome.DENIED: ShellStepState.DENIED,
    StepOutcome.UNAVAILABLE: ShellStepState.UNAVAILABLE,
    StepOutcome.CANCELLED: ShellStepState.CANCELLED,
    StepOutcome.EXPIRED: ShellStepState.EXPIRED,
}


def accepted_shell_snapshot(
    session_id: str, request_id: str, message: str = "Request accepted",
) -> ShellSessionSnapshot:
    return ShellSessionSnapshot(
        session_id, request_id, 0, ShellRunState.ACCEPTED, message=message
    )


def project_shell_snapshot(
    session_id: str,
    lifecycle: PlanInstanceSnapshot,
    shell_revision: int,
    *,
    approval: ShellApprovalRequest | None = None,
    result: TaskResult | None = None,
    message: str = "Working",
    cancelling: bool = False,
) -> ShellSessionSnapshot:
    if sum((approval is not None, result is not None, cancelling)) > 1:
        raise ValueError("shell projection authority states are exclusive")
    if shell_revision <= 0 or isinstance(shell_revision, bool):
        raise ValueError("projected shell revision must be positive")
    if result is not None and not lifecycle.terminal:
        raise ValueError("shell result requires terminal Core lifecycle")
    state = _run_state(approval, result, cancelling)
    steps = _steps(lifecycle, result is not None)
    return ShellSessionSnapshot(
        session_id,
        lifecycle.plan.request_id,
        shell_revision,
        state,
        steps,
        lifecycle.current_step_id,
        message,
        approval,
        _result(result),
    )


def _run_state(approval, result, cancelling):
    if result is not None:
        return ShellRunState.TERMINAL
    if approval is not None:
        return ShellRunState.WAITING_APPROVAL
    if cancelling:
        return ShellRunState.CANCELLING
    return ShellRunState.RUNNING


def _steps(snapshot, terminal):
    states = {
        event.source_step_id: OUTCOME_STATES[event.outcome]
        for event in snapshot.events[1:]
    }
    if terminal:
        states[snapshot.current_step_id] = _terminal_state(snapshot.terminal_disposition)
    else:
        states[snapshot.current_step_id] = ShellStepState.ACTIVE
    return tuple(
        ShellPlanStep(
            step.step_id, step.kind.value, step.description,
            states.get(step.step_id, ShellStepState.PENDING),
        )
        for step in snapshot.plan.steps
    )


def _terminal_state(disposition):
    return {
        TerminalDisposition.RELEASE: ShellStepState.SUCCEEDED,
        TerminalDisposition.WITHHOLD: ShellStepState.DENIED,
        TerminalDisposition.FAIL: ShellStepState.FAILED,
    }[disposition]


def _result(result):
    if result is None:
        return None
    return ShellResult(
        result.request_id,
        result.status,
        result.content,
        result.reason,
        result.verified,
        result.evidence_ids,
    )
