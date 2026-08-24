"""Prepare and execute a real installed Expert Factory lifecycle."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast


SOURCE_RUN = "phase22-stable-toposort-diverse2500-chat-20260718-03"
SOURCE_JOB = f"{SOURCE_RUN}-job"
LLAMA_CPP_REVISION = "86d86ed4396b4130922f7b9af26e3d9fc11a591b"


class CandidateInstallation(Protocol):
    prefix: Path


def run_factory_scenario(
    *, installation: CandidateInstallation, repository: Path, root: Path, run_id: str,
    ollama_url: str,
) -> dict[str, object]:
    source = repository / "artifacts/training" / SOURCE_RUN
    training = root / "training-artifact"
    _stage_factory_state(source, training)
    output = root / "factory-result.json"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(installation.prefix / "active/python")
    command = (
        sys.executable,
        str(repository / "tools/phase23_installed_matrix/factory_process.py"),
        "--training-artifact", str(training),
        "--conversion-environment", str(
            repository / "artifacts/training/conversion/venv-36eb5cce"
        ),
        "--conversion-manifest", str(
            repository / "artifacts/training/conversion/wheelhouse-manifest.json"
        ),
        "--llama-cpp", str(repository / "artifacts/training/conversion/llama.cpp"),
        "--llama-cpp-revision", LLAMA_CPP_REVISION,
        "--model-directory", str(
            repository / "artifacts/training/models/Qwen3-1.7B-70d244cc"
        ),
        "--prompt-configuration", str(
            repository / "configs/benchmarks/full-workstation-verified-smoke.json"
        ),
        "--verifier-tests", str(
            repository / "tests/fixtures/verification/stable_topological_sort_tests.py"
        ),
        "--ollama", "/usr/local/bin/ollama", "--ollama-url", ollama_url,
        "--run-id", SOURCE_RUN, "--attempt-id", f"phase23-{run_id}",
        "--installation-prefix", str(installation.prefix),
        "--output", str(output),
    )
    log = root / "factory-process.log"
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            command, stdout=stream, stderr=subprocess.STDOUT, text=True,
            env=environment, timeout=7_200,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            "candidate Factory lifecycle failed: " + log.read_text(errors="replace")[-12000:]
        )
    return cast(dict[str, object], json.loads(output.read_text("utf-8")))


def _stage_factory_state(source: Path, target: Path) -> None:
    target.mkdir(parents=True, mode=0o700)
    shutil.copytree(source / "state", target / "state")
    source_job = source / "jobs" / SOURCE_JOB
    target_job = target / "jobs" / SOURCE_JOB
    target_job.parent.mkdir()
    shutil.copytree(source_job, target_job, copy_function=os.link)
