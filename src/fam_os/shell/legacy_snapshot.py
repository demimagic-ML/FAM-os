"""Frozen v1alpha1 Shell snapshot retained for exact decoding and migration."""

from dataclasses import dataclass

from fam_os.core.contracts import ResultStatus
from fam_os.shell.contracts import (
    ShellApprovalRequest,
    ShellPlanStep,
    ShellResult as CurrentShellResult,
    ShellRunState,
    ShellSessionSnapshot as CurrentShellSessionSnapshot,
    ShellStepState,
)


LEGACY_SHELL_SNAPSHOT_VERSION = "fam.shell/v1alpha1"


@dataclass(frozen=True, slots=True)
class ShellResult:
    request_id: str
    status: ResultStatus
    content: str | None
    reason: str = ""
    verified: bool = False
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("legacy Shell result identity is invalid")
        successful = self.status in {ResultStatus.COMPLETED, ResultStatus.VERIFIED}
        if successful != bool(self.content):
            raise ValueError("legacy Shell result content does not match status")
        if self.verified != (self.status is ResultStatus.VERIFIED):
            raise ValueError("legacy Shell result verification is invalid")
        if not successful and not self.reason.strip():
            raise ValueError("legacy Shell non-success requires a reason")
        if self.verified and not self.evidence_ids:
            raise ValueError("legacy verified Shell result requires evidence")


@dataclass(frozen=True, slots=True)
class ShellSessionSnapshot:
    session_id: str
    request_id: str
    revision: int
    state: ShellRunState
    steps: tuple[ShellPlanStep, ...] = ()
    current_step_id: str | None = None
    message: str = ""
    approval: ShellApprovalRequest | None = None
    result: ShellResult | None = None
    contract_version: str = LEGACY_SHELL_SNAPSHOT_VERSION

    def __post_init__(self) -> None:
        if not self.session_id.strip() or not self.request_id.strip():
            raise ValueError("legacy Shell snapshot identity is invalid")
        if self.revision < 0 or isinstance(self.revision, bool):
            raise ValueError("legacy Shell snapshot revision is invalid")
        if self.contract_version != LEGACY_SHELL_SNAPSHOT_VERSION:
            raise ValueError("legacy Shell snapshot version is invalid")
        step_ids = tuple(item.step_id for item in self.steps)
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("legacy Shell step identities are not unique")
        if self.current_step_id is not None and self.current_step_id not in step_ids:
            raise ValueError("legacy Shell current step is invalid")
        active = tuple(item for item in self.steps if item.state is ShellStepState.ACTIVE)
        if len(active) > 1 or (active and active[0].step_id != self.current_step_id):
            raise ValueError("legacy Shell active step is invalid")
        waiting = self.state is ShellRunState.WAITING_APPROVAL
        terminal = self.state is ShellRunState.TERMINAL
        if waiting != (self.approval is not None) or terminal != (self.result is not None):
            raise ValueError("legacy Shell authority surface is invalid")
        if self.result is not None and self.result.request_id != self.request_id:
            raise ValueError("legacy Shell result request is invalid")


def migrate_shell_snapshot_v1alpha1(
    value: ShellSessionSnapshot,
) -> CurrentShellSessionSnapshot:
    result = None
    if value.result is not None:
        old = value.result
        result = CurrentShellResult(
            old.request_id, old.status, old.content, old.reason,
            old.verified, old.evidence_ids,
        )
    return CurrentShellSessionSnapshot(
        value.session_id, value.request_id, value.revision, value.state,
        value.steps, value.current_step_id, value.message, value.approval, result,
    )
