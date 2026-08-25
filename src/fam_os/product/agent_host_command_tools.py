"""Resource-bounded host command execution for explicitly approved Full OS turns."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from fam_os.adapters.bubblewrap.process import ProcessLauncher, SubprocessProcessLauncher
from fam_os.core.agent import AgentToolDescriptor, AgentToolEffect, AgentToolRegistry
from fam_os.verification.sandbox import IsolationLevel, SandboxLimits, SandboxStatus


class HostCommandTools:
    """Execute direct argv with current-user host access after Full OS approval."""

    def __init__(
        self, workspace_root: Path, *, launcher: ProcessLauncher | None = None,
        limits: SandboxLimits = SandboxLimits(
            wall_seconds=120, memory_bytes=4 * 1024**3, cpu_seconds=120,
            file_bytes=2 * 1024**3, open_files=2_048, processes=512,
            output_bytes=262_144, unbounded_virtual_address_space=True,
        ),
    ) -> None:
        root = workspace_root.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise PermissionError("host command workspace must be a real directory")
        self.root = root
        self.launcher = launcher or SubprocessProcessLauncher()
        self.limits = limits

    def register(self, registry: AgentToolRegistry) -> None:
        registry.register(AgentToolDescriptor(
            "run_host_command",
            "Run direct argv with the current OS user's full host filesystem, process, "
            "and network access. This is not sandboxed and requires Full OS authority.",
            AgentToolEffect.OS_WRITE,
            {"type": "object", "properties": {
                "command": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "number"},
            }, "required": ["command"]},
        ), self.run_command)

    def run_command(self, arguments: dict[str, object]) -> str:
        if not set(arguments).issubset({"command", "timeout_seconds"}):
            raise ValueError("host command arguments contain unsupported fields")
        command = arguments.get("command")
        if (
            not isinstance(command, list) or not 1 <= len(command) <= 256
            or any(not isinstance(item, str) or not item or "\0" in item for item in command)
        ):
            raise ValueError("host command must be a non-empty argv array")
        timeout = arguments.get("timeout_seconds", self.limits.wall_seconds)
        if (
            not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
            or not 0 < float(timeout) <= 3_600
        ):
            raise ValueError("host command timeout is invalid")
        result = self.launcher.run(
            ("/usr/bin/env", "--chdir", str(self.root), *command),
            replace(self.limits, wall_seconds=float(timeout)),
            tuple(os.environ.items()), IsolationLevel.NONE,
        )
        if result.status is not SandboxStatus.COMPLETED:
            raise RuntimeError(
                f"status={result.status.value}\nreason={result.reason}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        output = (
            f"status=completed\nexit_code={result.exit_code}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        if result.exit_code != 0:
            raise RuntimeError(output)
        return output
