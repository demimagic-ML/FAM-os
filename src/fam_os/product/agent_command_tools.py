"""Workspace-bound command execution tools for the iterative agent."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fam_os.adapters.bubblewrap.discovery import (
    ExecutableLocator,
    PathExecutableLocator,
)
from fam_os.adapters.bubblewrap.process import (
    ProcessLauncher,
    SubprocessProcessLauncher,
)
from fam_os.adapters.bubblewrap.settings import BubblewrapSettings
from fam_os.core.agent import AgentToolDescriptor, AgentToolEffect, AgentToolRegistry
from fam_os.verification.sandbox import IsolationLevel, SandboxLimits, SandboxStatus


class WorkspaceCommandTools:
    def __init__(
        self,
        workspace_root: Path,
        *,
        settings: BubblewrapSettings = BubblewrapSettings(),
        locator: ExecutableLocator | None = None,
        launcher: ProcessLauncher | None = None,
        read_only_overlays: tuple[tuple[Path, Path], ...] = (),
        limits: SandboxLimits = SandboxLimits(
            wall_seconds=120,
            memory_bytes=2 * 1024**3,
            cpu_seconds=120,
            file_bytes=512 * 1024**2,
            open_files=1_024,
            processes=256,
            output_bytes=262_144,
            unbounded_virtual_address_space=True,
        ),
    ) -> None:
        root = workspace_root.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise PermissionError("command workspace must be a real directory")
        self.root = root
        self.settings = settings
        self.locator = locator or PathExecutableLocator()
        self.launcher = launcher or SubprocessProcessLauncher()
        self.limits = limits
        self.read_only_overlays = tuple(
            (source.resolve(strict=True), destination.absolute())
            for source, destination in read_only_overlays
        )
        if any(
            not source.is_dir()
            or destination == root
            or root not in destination.parents
            for source, destination in self.read_only_overlays
        ):
            raise PermissionError("command overlay must map a directory inside the workspace")

    def register(self, registry: AgentToolRegistry) -> None:
        registry.register(AgentToolDescriptor(
            "run_command",
            "Run an argv command in the writable workspace sandbox and return stdout, "
            "stderr, and exit status. The sandbox has system executables from /usr/bin "
            "and /bin, no network, no copied project virtual environment, and no "
            "permission to install into the host Python environment. Inspect project "
            "manifests and prefer already available runtimes and repository scripts.",
            AgentToolEffect.COMMAND,
            {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array", "items": {"type": "string"},
                    },
                    "timeout_seconds": {"type": "number"},
                },
                "required": ["command"],
            },
        ), self.run_command)

    def run_command(self, arguments: dict[str, object]) -> str:
        if not set(arguments).issubset({"command", "timeout_seconds"}):
            raise ValueError("run_command arguments contain unsupported fields")
        command = arguments.get("command")
        if (
            not isinstance(command, list)
            or not 1 <= len(command) <= 256
            or any(not isinstance(item, str) or not item or "\0" in item for item in command)
        ):
            raise ValueError("run_command command must be a non-empty argv array")
        timeout = arguments.get("timeout_seconds", self.limits.wall_seconds)
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not 0 < float(timeout) <= 3_600
        ):
            raise ValueError("run_command timeout is invalid")
        bubblewrap = self.locator.find(self.settings.bubblewrap_executable)
        if bubblewrap is None:
            raise RuntimeError("workspace command sandbox requires bubblewrap")
        sandbox_command = _bubblewrap_command(
            bubblewrap, self.root, tuple(command), self.settings,
            self.read_only_overlays,
        )
        limits = replace(self.limits, wall_seconds=float(timeout))
        result = self.launcher.run(
            sandbox_command, limits, self.settings.environment,
            IsolationLevel.BUBBLEWRAP,
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
            if "execvp" in result.stderr and "No such file" in result.stderr:
                hints = _executable_hints(command[0])
                if hints:
                    output += "\navailable_executable_examples=" + ",".join(hints)
            raise RuntimeError(output)
        return output


def _executable_hints(requested: str) -> tuple[str, ...]:
    """Return bounded real sandbox-visible alternatives for a missing executable."""
    name = Path(requested).name
    stem = name.rstrip("0123456789.-") or name
    values = []
    for directory in (Path("/usr/bin"), Path("/bin")):
        try:
            entries = directory.iterdir()
        except OSError:
            continue
        for path in entries:
            if (
                path.name.startswith(stem) and path.is_file()
                and path.stat().st_mode & 0o111
            ):
                values.append(str(path))
    return tuple(sorted(dict.fromkeys(values))[:8])


def _bubblewrap_command(
    bubblewrap: str,
    workspace: Path,
    command: tuple[str, ...],
    settings: BubblewrapSettings,
    read_only_overlays: tuple[tuple[Path, Path], ...] = (),
) -> tuple[str, ...]:
    root = str(workspace)
    values = [
        bubblewrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--cap-drop", "ALL",
    ]
    for path in settings.read_only_paths:
        values.extend(("--ro-bind", path, path))
    for path in settings.optional_read_only_paths:
        values.extend(("--ro-bind-try", path, path))
    values.extend((
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", settings.temporary_directory,
        "--bind", root, root,
    ))
    for source, destination in read_only_overlays:
        values.extend(("--ro-bind", str(source), str(destination)))
    values.extend((
        "--chdir", root,
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "HOME", settings.temporary_directory,
        "--setenv", "PYTHONHASHSEED", "0",
        "--",
        *command,
    ))
    return tuple(values)
