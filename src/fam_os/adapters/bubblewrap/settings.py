"""Explicit Bubblewrap adapter settings."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BubblewrapSettings:
    python_executable: str = "python3"
    bubblewrap_executable: str = "bwrap"
    systemd_run_executable: str = "systemd-run"
    require_bubblewrap: bool = True
    require_systemd_cgroup: bool = True
    read_only_paths: tuple[str, ...] = ("/usr", "/lib")
    optional_read_only_paths: tuple[str, ...] = ("/lib64",)
    temporary_directory: str = "/tmp"
    environment: tuple[tuple[str, str], ...] = (
        ("PATH", "/usr/bin:/bin"),
        ("PYTHONHASHSEED", "0"),
    )

    def __post_init__(self) -> None:
        if not self.python_executable or not self.bubblewrap_executable or not self.systemd_run_executable:
            raise ValueError("sandbox executable names must not be empty")
        paths = (*self.read_only_paths, *self.optional_read_only_paths)
        if any(not path.startswith("/") for path in paths):
            raise ValueError("sandbox bind paths must be absolute")
        if not self.temporary_directory.startswith("/"):
            raise ValueError("temporary_directory must be absolute")
