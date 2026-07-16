"""Installed composition entry point for the local FAM Shell client."""

import argparse
import os
from pathlib import Path

from fam_os.adapters.shell.client import (
    UnixShellClientConfiguration,
    UnixShellCoreClient,
)
from fam_os.shell.controller import ShellController
from fam_os.shell.terminal import TerminalShell, run_terminal


def default_socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(runtime) if runtime else Path(f"/run/user/{os.geteuid()}")
    return root / "fam-os" / "shell.sock"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FAM_OS local terminal shell")
    parser.add_argument("--socket", type=Path, default=default_socket_path())
    parser.add_argument("--timeout", type=float, default=10.0)
    arguments = parser.parse_args(argv)
    client = UnixShellCoreClient(
        UnixShellClientConfiguration(arguments.socket.absolute(), arguments.timeout)
    )
    return run_terminal(TerminalShell(ShellController(client)))


if __name__ == "__main__":
    raise SystemExit(main())
