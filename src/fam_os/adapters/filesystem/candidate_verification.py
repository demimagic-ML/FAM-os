"""Shell-free bounded verification rooted in an isolated candidate workspace."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.filesystem.candidate_io import contained
from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.core.engineering.transactions import CandidateWorkspace


@dataclass(frozen=True, slots=True)
class CandidateVerificationEvidence:
    candidate_id: str
    command: tuple[str, ...]
    working_directory: str
    exit_code: int | None
    stdout_sha256: str
    stderr_sha256: str
    timed_out: bool
    output_limited: bool

    @property
    def passed(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.output_limited
        )


class CandidateVerificationAdapter:
    def __init__(self, allowed_executables: tuple[Path, ...], runner=None) -> None:
        if not allowed_executables or any(
            not path.is_absolute() or not path.is_file()
            for path in allowed_executables
        ):
            raise ValueError("candidate verifier requires absolute existing executables")
        self._allowed = frozenset(str(path) for path in allowed_executables)
        self._runner = runner or BoundedSubprocessRunner()

    def run(
        self,
        candidate: CandidateWorkspace,
        command: tuple[str, ...],
        *,
        working_directory: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> CandidateVerificationEvidence:
        if not command or command[0] not in self._allowed:
            raise PermissionError("candidate verification executable is not allowed")
        root = Path(candidate.candidate_workspace)
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise PermissionError("candidate verification root is invalid")
        cwd = root if working_directory is None else contained(root, working_directory)
        if not cwd.is_dir() or cwd.is_symlink():
            raise PermissionError("candidate verification cwd is invalid")
        result = self._runner.run(command, cwd=cwd, environment=environment or {})
        return CandidateVerificationEvidence(
            candidate.candidate_id, command, str(cwd), result.exit_code,
            _digest(result.stdout), _digest(result.stderr), result.timed_out,
            result.output_limited,
        )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
