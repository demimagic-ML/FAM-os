"""Bubblewrap implementation of the sandbox runner port."""

from dataclasses import dataclass, field

from fam_os.adapters.bubblewrap.commands import (
    build_bubblewrap_command,
    build_python_command,
    build_systemd_sandbox_command,
)
from fam_os.adapters.bubblewrap.discovery import ExecutableLocator, PathExecutableLocator
from fam_os.adapters.bubblewrap.process import ProcessLauncher, SubprocessProcessLauncher
from fam_os.adapters.bubblewrap.settings import BubblewrapSettings
from fam_os.verification.sandbox import (
    IsolationLevel,
    SandboxRequest,
    SandboxResult,
    SandboxStatus,
)


@dataclass(slots=True)
class BubblewrapSandboxRunner:
    settings: BubblewrapSettings = BubblewrapSettings()
    locator: ExecutableLocator = field(default_factory=PathExecutableLocator)
    launcher: ProcessLauncher = field(default_factory=SubprocessProcessLauncher)

    def run(self, request: SandboxRequest) -> SandboxResult:
        python = self.locator.find(self.settings.python_executable)
        if python is None:
            return _unavailable("Python executable is unavailable")
        bubblewrap = self.locator.find(self.settings.bubblewrap_executable)
        if bubblewrap is None and self.settings.require_bubblewrap:
            return _unavailable("Bubblewrap isolation is required but unavailable")
        if bubblewrap is None:
            command = build_python_command(python, request.script)
            isolation = IsolationLevel.PROCESS_LIMITS
        else:
            systemd_run = self.locator.find(self.settings.systemd_run_executable)
            if systemd_run is None and self.settings.require_systemd_cgroup:
                return _unavailable("systemd cgroup sandbox wrapper is required but unavailable")
            command = build_bubblewrap_command(
                bubblewrap, python, request.script, self.settings
            )
            if systemd_run is not None:
                command = build_systemd_sandbox_command(systemd_run, command, request.limits)
            isolation = IsolationLevel.BUBBLEWRAP
        result = self.launcher.run(
            command, request.limits, self.settings.environment, isolation
        )
        if isolation is IsolationLevel.BUBBLEWRAP and _bubblewrap_failed_to_start(result):
            return _unavailable("Bubblewrap could not establish the required namespaces")
        return result


def _unavailable(reason: str) -> SandboxResult:
    return SandboxResult(
        status=SandboxStatus.UNAVAILABLE,
        isolation=IsolationLevel.NONE,
        wall_seconds=0,
        reason=reason,
    )


def _bubblewrap_failed_to_start(result: SandboxResult) -> bool:
    return (
        result.status is SandboxStatus.COMPLETED
        and result.exit_code != 0
        and result.stderr.lstrip().startswith("bwrap:")
    )
