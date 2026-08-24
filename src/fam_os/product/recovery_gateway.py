"""Read-only Shell surface while product storage requires recovery."""

from __future__ import annotations

from threading import Lock

from fam_os.core.contracts import ResultStatus
from fam_os.shell import (
    ShellPlanStep,
    ShellResult,
    ShellRunState,
    ShellSessionSnapshot,
    ShellStepState,
)


class RecoveryModeShellGateway:
    def __init__(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("recovery gateway requires a safe reason")
        self._reason = reason
        self._sessions: dict[str, ShellSessionSnapshot] = {}
        self._lock = Lock()

    def ask(self, command) -> ShellSessionSnapshot:
        session_id = f"recovery-{command.request_id}"
        snapshot = ShellSessionSnapshot(
            session_id,
            command.request_id,
            0,
            ShellRunState.TERMINAL,
            (
                ShellPlanStep(
                    "recovery", "recovery_required", "Normal tasks are disabled",
                    ShellStepState.UNAVAILABLE,
                ),
            ),
            message=self._reason,
            result=ShellResult(
                command.request_id,
                ResultStatus.FAILED,
                None,
                f"FAM_OS recovery mode: {self._reason}",
            ),
        )
        with self._lock:
            self._sessions[session_id] = snapshot
        return snapshot

    def snapshot(self, session_id: str) -> ShellSessionSnapshot:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as error:
                raise KeyError("recovery session does not exist") from error

    def decide(self, _command):
        raise ValueError("recovery mode does not accept action decisions")

    def cancel(self, command) -> ShellSessionSnapshot:
        return self.snapshot(command.session_id)
