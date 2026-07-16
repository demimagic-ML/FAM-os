"""Pure isolated Python command construction."""

from fam_os.adapters.bubblewrap.settings import BubblewrapSettings
from fam_os.verification.sandbox import SandboxLimits


def build_python_command(python: str, script: str) -> tuple[str, ...]:
    return python, "-I", "-S", "-c", script


def build_bubblewrap_command(
    bubblewrap: str, python: str, script: str, settings: BubblewrapSettings
) -> tuple[str, ...]:
    command = [
        bubblewrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--cap-drop",
        "ALL",
    ]
    for path in settings.read_only_paths:
        command.extend(("--ro-bind", path, path))
    for path in settings.optional_read_only_paths:
        command.extend(("--ro-bind-try", path, path))
    temporary = settings.temporary_directory
    command.extend(
        (
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            temporary,
            "--chdir",
            temporary,
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "PYTHONHASHSEED",
            "0",
        )
    )
    command.extend(build_python_command(python, script))
    return tuple(command)


def build_systemd_sandbox_command(
    systemd_run: str, command: tuple[str, ...], limits: SandboxLimits
) -> tuple[str, ...]:
    return (
        systemd_run, "--user", "--scope", "--quiet",
        "-p", f"TasksMax={limits.processes}",
        "-p", f"MemoryMax={limits.memory_bytes}",
        "-p", "MemorySwapMax=0",
        "--", *command,
    )
