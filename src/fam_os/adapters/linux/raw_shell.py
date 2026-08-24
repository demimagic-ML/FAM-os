"""Exact-command raw shell adapter for explicit single-use owner grants."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.core.engineering.execution import (
    EngineeringToolReceipt, RawShellAuthorization, ToolQualificationStatus,
)
from fam_os.core.engineering.execution_policy import RawShellGate
from fam_os.core.engineering.diagnostic_redaction import (
    sanitize_diagnostic_evidence,
)
from fam_os.core.engineering.grants import EngineeringAuthorityGrant


class RawShellExecutionAdapter:
    def __init__(self, runner=None, gate=None, clock=None) -> None:
        self._runner = runner or BoundedSubprocessRunner()
        self._gate = gate or RawShellGate()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._consumed: set[str] = set()

    def run(
        self,
        authorization: RawShellAuthorization,
        grant: EngineeringAuthorityGrant,
        command: bytes,
        *,
        principal_id: str,
        task_id: str,
        workspace_root: Path,
        candidate_id: str,
    ) -> EngineeringToolReceipt:
        started = self._clock()
        self._gate.authorize(
            authorization, grant, command, principal_id=principal_id,
            task_id=task_id, workspace_root=str(workspace_root), instant=started,
        )
        if authorization.authorization_id in self._consumed:
            raise PermissionError("raw shell authorization is consumed")
        if not workspace_root.is_absolute() or not workspace_root.is_dir() or workspace_root.is_symlink():
            raise PermissionError("raw shell workspace is invalid")
        try:
            decoded = command.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("raw shell command must be UTF-8") from error
        result = self._runner.run(
            (authorization.shell_executable, "-c", decoded),
            cwd=workspace_root, environment=dict(authorization.environment),
        )
        self._consumed.add(authorization.authorization_id)
        completed = self._clock()
        status = ToolQualificationStatus.PASSED if result.succeeded else ToolQualificationStatus.FAILED
        return EngineeringToolReceipt(
            f"raw-shell-receipt-{uuid4().hex}", task_id, candidate_id,
            "raw-shell.explicit", authorization.command_sha256,
            authorization.privilege_tier.value, authorization.command_sha256,
            started, completed, result.exit_code, _digest(result.stdout),
            _digest(result.stderr), (), (), ("exact-owner-raw-shell-grant",),
            status, sanitize_diagnostic_evidence(result.stdout + result.stderr),
        )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
