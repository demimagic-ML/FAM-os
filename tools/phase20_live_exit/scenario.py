"""Host orchestration and deterministic response script for Phase 20.6."""

from __future__ import annotations

import json
import subprocess
import sys


PRIMARY = "qwen2.5-coder:7b"
STRONG = "gemma4:26b"
OUTPUTS = tuple(f"PHASE20_LIVE_VERIFIED_{index}" for index in range(1, 7))
PROMPTS = tuple(
    f"Write Python code for a repeated test; reply exactly {output}"
    for output in OUTPUTS
)
REDACTION = "[terminal content removed after result retention]"


def scripted_responses() -> tuple[dict, ...]:
    return (
        _response(PRIMARY, OUTPUTS[0]),
        _response(PRIMARY, "wrong-live-2-primary"),
        _response(PRIMARY, "wrong-live-2-repair"),
        _response(STRONG, OUTPUTS[1]),
        _response(PRIMARY, OUTPUTS[2]),
        _response(PRIMARY, "wrong-live-4-primary"),
        _response(PRIMARY, "wrong-live-4-repair"),
        _response(STRONG, OUTPUTS[3]),
        _response(PRIMARY, OUTPUTS[4]),
        _response(STRONG, OUTPUTS[5]),
    )


def run_client(installation, repository, service, mode: str) -> dict:
    output = service.run_root / f"client-{mode}.json"
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase20_live_exit/client_process.py"),
            "--installed-python",
            str(installation.prefix / "active/python"),
            "--repository",
            str(repository),
            "--socket",
            str(service.runtime_root / "shell.sock"),
            "--mode",
            mode,
            "--output",
            str(output),
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def inspect_state(
    installation,
    repository,
    product_root,
    output,
    request_count: int = 6,
) -> dict:
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase20_live_exit/inspect_process.py"),
            "--installed-python",
            str(installation.prefix / "active/python"),
            "--repository",
            str(repository),
            "--state-root",
            str(product_root / "state"),
            "--output",
            str(output),
            "--request-count",
            str(request_count),
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _response(model_ref: str, content: str) -> dict:
    return {"model_ref": model_ref, "content": content}
