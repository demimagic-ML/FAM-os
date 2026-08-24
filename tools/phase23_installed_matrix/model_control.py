"""Apply signed expert enablement policy using the installed candidate code."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def restrict_candidate_experts(
    installation, repository: Path, state_root: Path, output: Path, model_ref: str,
) -> dict[str, object]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(installation.prefix / "active/python")
    completed = subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase23_installed_matrix/model_control_process.py"),
            "--state-root", str(state_root), "--model-ref", model_ref,
            "--output", str(output),
        ),
        env=environment, capture_output=True, text=True, timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "installed candidate expert restriction failed: "
            + completed.stderr[-6000:]
        )
    document = json.loads(output.read_text("utf-8"))
    candidate_root = (installation.prefix / "active/python").resolve()
    if not Path(document["candidate_module"]).resolve().is_relative_to(candidate_root):
        raise RuntimeError("expert restriction did not import the installed candidate")
    return document
