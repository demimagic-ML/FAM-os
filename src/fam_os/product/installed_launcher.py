"""Stable installed launchers independent of a disposable build environment."""

import os
from pathlib import Path
import sys


def installed_launcher(prefix: Path, module: str, runtime_python: str) -> str:
    return (
        "#!/bin/sh\nset -eu\n"
        f"PYTHONPATH='{prefix}/active/python' exec '{runtime_python}' "
        f"-m {module} \"$@\"\n"
    )


def stable_runtime_python() -> str:
    """Resolve the base interpreter, never a disposable builder virtualenv."""
    value = getattr(sys, "_base_executable", None) or sys.executable
    path = Path(value)
    if not path.is_absolute():
        raise RuntimeError("installation runtime Python must be absolute")
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise RuntimeError("installation runtime Python is unavailable")
    return str(resolved)
