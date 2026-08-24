"""Clean-environment installed CLI and candidate probes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def clean_environment(home: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
    })
    return environment


def source_install(
    *, repository: Path, prefix: Path, bundle: Path,
    key_id: str, key_path: Path, environment: dict[str, str],
) -> dict[str, Any]:
    source_environment = {**environment, "PYTHONPATH": str(repository / "src")}
    return _json_command((
        sys.executable, "-m", "fam_os.product.cli",
        "--prefix", str(prefix),
        "--trusted-key", f"{key_id}={key_path}",
        "install", "--bundle", str(bundle),
    ), source_environment, environment["HOME"])


def installed_cli(
    prefix: Path, arguments: tuple[str, ...], environment: dict[str, str],
    *, accepted_codes: tuple[int, ...] = (0,),
) -> dict[str, Any]:
    return _json_command(
        (str(prefix / "bin/fam-os"), "--prefix", str(prefix), *arguments),
        environment, environment["HOME"], accepted_codes=accepted_codes,
    )


def _json_command(
    command: tuple[str, ...], environment: dict[str, str], cwd: str,
    *, accepted_codes: tuple[int, ...] = (0,),
) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=cwd, env=environment, check=False,
        capture_output=True, text=True, timeout=600,
    )
    if completed.returncode not in accepted_codes:
        raise RuntimeError(
            f"lifecycle command returned {completed.returncode}: "
            + completed.stderr[-1000:]
        )
    lines = tuple(line for line in completed.stdout.splitlines() if line.strip())
    if not lines:
        raise RuntimeError("lifecycle command returned no JSON receipt")
    document = json.loads(lines[-1])
    if not isinstance(document, dict):
        raise TypeError("lifecycle command receipt must be an object")
    return document
