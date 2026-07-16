"""Local transport adapters for the unprivileged FAM Shell."""

from fam_os.adapters.shell.client import (
    UnixShellClientConfiguration,
    UnixShellCoreClient,
)
from fam_os.adapters.shell.dispatcher import ShellRequestDispatcher
from fam_os.adapters.shell.server import (
    UnixShellServer,
    UnixShellServerConfiguration,
)

__all__ = [
    "ShellRequestDispatcher",
    "UnixShellClientConfiguration",
    "UnixShellCoreClient",
    "UnixShellServer",
    "UnixShellServerConfiguration",
]
