"""Unprivileged local FAM Shell contracts and controller."""

from fam_os.shell.contracts import (
    SHELL_CONTRACT_VERSION,
    ShellApprovalRequest,
    ShellAskCommand,
    ShellCancelCommand,
    ShellContext,
    ShellContextKind,
    ShellDecision,
    ShellDecisionCommand,
    ShellPlanStep,
    ShellResult,
    ShellRunState,
    ShellSessionSnapshot,
    ShellSnapshotQuery,
    ShellStepState,
)
from fam_os.shell.controller import ShellController
from fam_os.shell.ports import ShellCoreClient, ShellCoreGateway
from fam_os.shell.render import render_contexts, render_snapshot
from fam_os.shell.terminal import TerminalShell, run_terminal

__all__ = [
    "SHELL_CONTRACT_VERSION",
    "ShellApprovalRequest",
    "ShellAskCommand",
    "ShellCancelCommand",
    "ShellContext",
    "ShellContextKind",
    "ShellController",
    "ShellCoreClient",
    "ShellCoreGateway",
    "ShellDecision",
    "ShellDecisionCommand",
    "ShellPlanStep",
    "ShellResult",
    "ShellRunState",
    "ShellSessionSnapshot",
    "ShellSnapshotQuery",
    "ShellStepState",
    "TerminalShell",
    "render_contexts",
    "render_snapshot",
    "run_terminal",
]
