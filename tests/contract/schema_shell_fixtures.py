from datetime import datetime, timezone

from fam_os.shell import (
    ShellApprovalRequest,
    ShellAskCommand,
    ShellCancelCommand,
    ShellContext,
    ShellContextKind,
    ShellDecision,
    ShellDecisionCommand,
    ShellPlanStep,
    ShellRunState,
    ShellSessionSnapshot,
    ShellSnapshotQuery,
    ShellStepState,
)


def shell_schema_values() -> tuple[object, ...]:
    context = ShellContext(
        "context-1", ShellContextKind.APPLICATION, "app:editor", "Editor",
        ("editor.observe",),
    )
    approval = ShellApprovalRequest(
        "approval-1", "proposal-1", "editor.write", "Apply edit",
        datetime(2026, 7, 18, tzinfo=timezone.utc), True,
    )
    snapshot = ShellSessionSnapshot(
        "session-1", "request-1", 1, ShellRunState.WAITING_APPROVAL,
        steps=(ShellPlanStep(
            "edit", "execute_action", "Apply edit", ShellStepState.ACTIVE,
        ),),
        current_step_id="edit", message="Prepared", approval=approval,
    )
    return (
        ShellAskCommand(
            "request-1", "Review this", (context,), ("editor.observe",), True,
        ),
        ShellSnapshotQuery("session-1"),
        ShellDecisionCommand(
            "session-1", 1, "approval-1", ShellDecision.APPROVE,
        ),
        ShellCancelCommand("session-1", 1),
        snapshot,
    )
