"""Composition entry point for the installed Console launcher command."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from fam_os.adapters.linux.console_browser import (
    LoopbackConsoleProbe,
    XdgConsoleBrowser,
)
from fam_os.product.console_launch import ConsoleLaunchService


def run_console_command(runtime_root: Path, port: int) -> int:
    receipt = ConsoleLaunchService(
        LoopbackConsoleProbe(), XdgConsoleBrowser(),
    ).launch(runtime_root.absolute(), port)
    print(json.dumps(asdict(receipt), sort_keys=True))
    return 0
